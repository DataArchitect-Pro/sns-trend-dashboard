import pandas as pd
import numpy as np
import networkx as nx
import math
from collections import defaultdict
from itertools import combinations
from sklearn.preprocessing import RobustScaler, MinMaxScaler
from janome.tokenizer import Tokenizer

# ==========================================
# 0. 初期設定（NLP・辞書）
# ==========================================
tokenizer = Tokenizer()

# 実務ではこれを外部の辞書ファイル（CSV等）で管理します
STOP_WORDS = {'こと', 'もの', 'これ', 'それ', '今日', 'さん', 'ちゃん', 'ため', 'よう', 'ところ', 'マジ', 'の', 'ん'}
MAGIC_WORDS = {'とは', '違い', 'おすすめ', '比較', '理由', 'メリット', 'デメリット', 'やり方', '始め方', '初心者', '解説', 'まとめ'}

# ==========================================
# 1. データ取得（本番を模した生テキスト生成）
# ==========================================
def fetch_raw_posts() -> pd.DataFrame:
    """本番のAPI取得を模した、生の投稿テキストデータ"""
    posts = []
    
    # パターン1: 次に来るトレンド（ブルーオーシャン / 比較・解説）
    for i in range(50):
        posts.append({"id": f"A{i}", "platform": "X", "text": "新しい画像生成AIの NanoBanana とは？ 始め方 を解説。", "eng": 25})
    for i in range(30):
        posts.append({"id": f"B{i}", "platform": "YouTube", "text": "Python と JavaScript の 違い を 比較 。初心者 に おすすめ です。", "eng": 40})
        
    # パターン2: 覇権エンタメ（レッドオーシャン）
    for i in range(500):
        posts.append({"id": f"C{i}", "platform": "X", "text": "覇権アニメ の最新話、 最高 だった。伏線の 理由 を 考察 してみた。", "eng": 150})
        posts.append({"id": f"D{i}", "platform": "YouTube", "text": "覇権アニメ の まとめ 動画です。", "eng": 300})
        
    # パターン3: スパム群（外れ値）
    for i in range(2000):
        posts.append({"id": f"E{i}", "platform": "X", "text": "アマギフ プレゼント！ フォロー と RT をお願いします！", "eng": 0})
        
    # パターン4: 日常語（ノイズ）
    for i in range(300):
        posts.append({"id": f"F{i}", "platform": "X", "text": "今日 の 仕事 疲れた。 帰宅 します。", "eng": 2})

    return pd.DataFrame(posts)

def get_historical_metrics(tokens: list) -> dict:
    """本来はDBから取得する過去データ（今回はモック関数）"""
    hist = {}
    for t in tokens:
        if t in ['覇権アニメ', '仕事', 'アマギフ']: 
            hist[t] = {'freq_past': 500, 'freq_14d': 5000, 'days_7d': 7, 'days_30d': 30}
        elif t in ['Python', 'JavaScript']:
            hist[t] = {'freq_past': 20, 'freq_14d': 200, 'days_7d': 5, 'days_30d': 15}
        else: # NanoBanana等の完全新規ワード
            hist[t] = {'freq_past': 0, 'freq_14d': 0, 'days_7d': 1, 'days_30d': 1}
    return hist

# ==========================================
# 2. NLPパイプライン（形態素解析）
# ==========================================
def extract_tokens(text: str) -> list:
    """テキストから意味のある名詞（トークン）を抽出する"""
    tokens = []
    for token in tokenizer.tokenize(text):
        if token.part_of_speech.startswith('名詞'):
            word = token.surface
            if len(word) > 1 and word not in STOP_WORDS:
                tokens.append(word)
    # 同一投稿内の重複を排除して返す
    return list(set(tokens))

# ==========================================
# 3. ネットワーク分析パイプライン
# ==========================================
def compute_network_and_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    """生データからグラフを構築し、全特徴量を計算する"""
    total_posts = len(df_raw)
    
    # 1. トークン化と基礎集計
    word_counts = defaultdict(int)
    pair_counts = defaultdict(int)
    word_eng = defaultdict(int)
    word_platforms = defaultdict(lambda: {'X': 0, 'YouTube': 0})
    
    for _, row in df_raw.iterrows():
        tokens = extract_tokens(row['text'])
        for w in tokens:
            word_counts[w] += 1
            word_eng[w] += row['eng']
            word_platforms[w][row['platform']] += 1
        # 共起ペアのカウント
        for w1, w2 in combinations(sorted(tokens), 2):
            pair_counts[(w1, w2)] += 1

    # 2. 共起グラフの構築と NPMI の計算
    G = nx.Graph()
    for (w1, w2), count in pair_counts.items():
        if count >= 3: # ノイズ排除: 3回以上共起したペアのみエッジを張る
            p_x = word_counts[w1] / total_posts
            p_y = word_counts[w2] / total_posts
            p_xy = count / total_posts
            
            pmi = math.log10(p_xy / (p_x * p_y))
            npmi = pmi / -math.log10(p_xy)
            
            if npmi > 0.1: # 有意な共起のみグラフに追加
                G.add_edge(w1, w2, weight=npmi, distance=1.0/npmi)

    # 3. 中心性の計算 (NetworkX)
    k_val = min(50, len(G.nodes))
    betweenness = nx.betweenness_centrality(G, k=k_val, weight='distance') if len(G) > 0 else {}
    
    degree_centrality = {}
    for node in G.nodes:
        degree_centrality[node] = sum(data['weight'] for _, _, data in G.edges(node, data=True))

    # 4. 履歴データの取得
    unique_tokens = list(word_counts.keys())
    hist_db = get_historical_metrics(unique_tokens)

    # 5. 特徴量DataFrameの構築
    features = []
    for w in unique_tokens:
        if word_counts[w] < 5: continue # 頻度5未満の足切り
        
        # 媒体横断性
        fx = word_platforms[w]['X']
        fyt = word_platforms[w]['YouTube']
        cross_platform_raw = (2 * min(fx, fyt)) / (fx + fyt + 1)
        
        # マジックワードとの最大NPMI (Conversion)
        max_conversion = 0.0
        for mw in MAGIC_WORDS:
            if G.has_edge(w, mw):
                max_conversion = max(max_conversion, G[w][mw]['weight'])
                
        # 履歴メトリクス
        hist = hist_db.get(w, {})
        freq_past = hist.get('freq_past', 0)
        freq_14d = hist.get('freq_14d', 0)
        
        features.append({
            'token': w,
            'freq_raw': word_counts[w],
            'growth_raw': (word_counts[w] + 5) / (freq_past + 5),
            'centrality_raw': degree_centrality.get(w, 0.0),
            'engagement_raw': word_eng[w] / word_counts[w], # 1投稿あたりの平均熱量
            'bridge_raw': betweenness.get(w, 0.0),
            'cross_platform_raw': cross_platform_raw,
            'sustainability_raw': hist.get('days_7d', 1) / 7.0,
            'noise_risk_raw': hist.get('days_30d', 1) / 30.0,
            'novelty_raw': max(0.0, 1.0 - (freq_14d / 100.0)),
            'conversion_raw': max_conversion
        })
        
    return pd.DataFrame(features)

# ==========================================
# 4. スケーリングとスコア計算 (前回FIX済みの堅牢なコード)
# ==========================================
def standardize_features(df_features: pd.DataFrame) -> pd.DataFrame:
    if df_features.empty: return df_features
    df = df_features.copy()
    
    df['freq_log'] = np.log1p(df['freq_raw'].fillna(0))
    df['engagement_log'] = np.log1p(df['engagement_raw'].fillna(0))
    
    target_cols = ['freq_log', 'growth_raw', 'centrality_raw', 'engagement_log']
    robust = RobustScaler()
    minmax = MinMaxScaler(feature_range=(0, 1))
    
    for col in target_cols:
        vals = df[[col]].fillna(0).values
        robust_vals = robust.fit_transform(vals)
        robust_vals_clipped = np.clip(robust_vals, a_min=None, a_max=3.0)
        new_col_name = col.replace('_raw', '_z').replace('_log', '_z')
        df[new_col_name] = minmax.fit_transform(robust_vals_clipped)

    bridge_vals = df[['bridge_raw']].fillna(0).values
    df['bridge_z'] = minmax.fit_transform(bridge_vals)

    df['cross_platform_z'] = df['cross_platform_raw'].fillna(0).clip(0, 1)
    df['sustainability_z'] = df['sustainability_raw'].fillna(0).clip(0, 1)
    df['noise_risk_z']     = df['noise_risk_raw'].fillna(0).clip(0, 1)
    df['novelty_z']        = df['novelty_raw'].fillna(0).clip(0, 1)
    df['conversion_z']     = df['conversion_raw'].fillna(0).clip(0, 1)
    
    return df

def compute_scores(df_z: pd.DataFrame) -> pd.DataFrame:
    if df_z.empty: return df_z
    df = df_z.copy()
    df['score_css'] = (
        0.32 * df['freq_z'] + 0.20 * df['growth_z'] + 0.18 * df['centrality_z'] +
        0.15 * df['cross_platform_z'] + 0.10 * df['engagement_z'] + 
        0.05 * df['sustainability_z'] - 0.10 * df['noise_risk_z']
    ) * 100

    df['score_eos'] = (
        0.26 * df['growth_z'] + 0.22 * df['novelty_z'] + 0.18 * df['bridge_z'] +
        0.16 * df['conversion_z'] + 0.10 * df['sustainability_z'] +
        0.08 * df['cross_platform_z'] + 0.05 * df['freq_z'] - 0.15 * df['noise_risk_z']
    ) * 100

    df['score_css'] = df['score_css'].clip(0, 100).round(1)
    df['score_eos'] = df['score_eos'].clip(0, 100).round(1)
    return df

def apply_decision_rules(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df['is_noise'] = df['noise_risk_z'] >= 0.8
    df['is_high_css'] = (df['score_css'] >= 50) & (~df['is_noise'])
    df['is_high_eos'] = (df['score_eos'] >= 60) & (~df['is_noise'])
    df['is_explainer'] = df['conversion_z'] >= 0.5
    df['is_comparative'] = df['bridge_z'] >= 0.5

    def generate_text(row):
        kw = row['token']
        if row['is_noise'] or kw in MAGIC_WORDS: # マジックワード単体は提案しない
            return "見送り", ""
        if row['is_comparative']:
            return "比較型", f"📊【徹底比較】「{kw}」と競合の違い・おすすめまとめ"
        elif row['is_high_css'] and row['is_explainer']:
            return "解説型", f"🚨【急上昇】今さら聞けない「{kw}」とは？3分で解説"
        elif row['is_high_eos'] and row['novelty_z'] >= 0.6:
            return "先読み型", f"💡【次に来る】そろそろ知っておきたい「{kw}」の始め方"
        elif row['is_high_css']:
            return "まとめ型", f"📝【まとめ】バズり中の「{kw}」、みんなの反応一覧"
        elif row['is_high_eos']:
            return "注目型", f"🔍【注目】局地的に話題の「{kw}」をチェック"
        return "見送り", ""

    df[['text_content_type', 'text_title_seed']] = df.apply(
        lambda r: pd.Series(generate_text(r)), axis=1
    )
    return df

# ==========================================
# 5. メインパイプライン
# ==========================================
def run_pipeline() -> pd.DataFrame:
    df_raw = fetch_raw_posts()
    df_features = compute_network_and_features(df_raw)
    df_z = standardize_features(df_features)
    df_scored = compute_scores(df_z)
    df_final = apply_decision_rules(df_scored)
    return df_final
