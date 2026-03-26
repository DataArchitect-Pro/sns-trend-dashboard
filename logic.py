import pandas as pd
import numpy as np
import networkx as nx
import math
import re  # 正規表現モジュールを追加
from collections import defaultdict
from itertools import combinations
from sklearn.preprocessing import RobustScaler, MinMaxScaler
from janome.tokenizer import Tokenizer

# ==========================================
# 0. 初期設定（NLP・辞書）
# ==========================================
tokenizer = Tokenizer()

# 【修正】ノイズになりやすいSNS特有の語を大幅追加
STOP_WORDS = {
    'こと', 'もの', 'これ', 'それ', '今日', 'さん', 'ちゃん', 'ため', 'よう', 'ところ', 
    'マジ', 'の', 'ん', 'お願い', '動画', '最新', '話', 'みんな', '反応', '一覧', '最高'
}
MAGIC_WORDS = {'とは', '違い', 'おすすめ', '比較', '理由', 'メリット', 'デメリット', 'やり方', '始め方', '初心者', '解説', 'まとめ'}

# ==========================================
# 1. データ取得（変更なし）
# ==========================================
def fetch_raw_posts() -> pd.DataFrame:
    posts = []
    for i in range(50):
        posts.append({"id": f"A{i}", "platform": "X", "text": "新しい画像生成AIの NanoBanana とは？ 始め方 を解説。", "eng": 25})
    for i in range(30):
        posts.append({"id": f"B{i}", "platform": "YouTube", "text": "Python と JavaScript の 違い を 比較 。初心者 に おすすめ です。", "eng": 40})
    for i in range(500):
        posts.append({"id": f"C{i}", "platform": "X", "text": "覇権アニメ の最新話、 最高 だった。伏線の 理由 を 考察 してみた。", "eng": 150})
        posts.append({"id": f"D{i}", "platform": "YouTube", "text": "覇権アニメ の まとめ 動画です。", "eng": 300})
    for i in range(2000):
        posts.append({"id": f"E{i}", "platform": "X", "text": "アマギフ プレゼント！ フォロー と RT をお願いします！", "eng": 0})
    for i in range(300):
        posts.append({"id": f"F{i}", "platform": "X", "text": "今日 の 仕事 疲れた。 帰宅 します。", "eng": 2})
    return pd.DataFrame(posts)

def get_historical_metrics(tokens: list) -> dict:
    """本来はDBから取得する過去データ（ダミー設定を修正）"""
    hist = {}
    for t in tokens:
        if 'NanoBanana' in t or '画像生成AI' in t:
            # 本当の次に来るワード（過去の出現0回の完全新規トレンド）
            hist[t] = {'freq_past': 0, 'freq_14d': 0, 'days_7d': 1, 'days_30d': 1}
        elif t in ['Python', 'JavaScript']:
            # 安定した技術ワード
            hist[t] = {'freq_past': 20, 'freq_14d': 200, 'days_7d': 5, 'days_30d': 15}
        else:
            # ★修正ポイント★
            # 覇権アニメ関連（伏線、考察、最新話）や日常語（帰宅）など、
            # 上記以外はすべて「昔からよく使われている常連語」として扱う。
            # これにより、無駄に新規性(novelty)と成長率(growth)が高騰するのを防ぐ。
            hist[t] = {'freq_past': 500, 'freq_14d': 5000, 'days_7d': 7, 'days_30d': 30}
    return hist

# ==========================================
# 2. NLPパイプライン（形態素解析の強化）
# ==========================================
def extract_tokens(text: str) -> list:
    """名詞が連続した場合、1つの「複合名詞」として結合して抽出する"""
    tokens = []
    current_compound = ""
    
    for token in tokenizer.tokenize(text):
        if token.part_of_speech.startswith('名詞'):
            current_compound += token.surface # 名詞が続く限り文字を繋げる
        else:
            if current_compound:
                if len(current_compound) > 1 and current_compound not in STOP_WORDS:
                    tokens.append(current_compound)
                current_compound = ""
                
    if current_compound: # 最後の単語の処理
        if len(current_compound) > 1 and current_compound not in STOP_WORDS:
            tokens.append(current_compound)
            
    return list(set(tokens))

# ==========================================
# 3. ネットワーク分析パイプライン（スパムフィルタ追加）
# ==========================================
def compute_network_and_features(df_raw: pd.DataFrame) -> pd.DataFrame:
    total_posts = len(df_raw)
    word_counts = defaultdict(int)
    pair_counts = defaultdict(int)
    word_eng = defaultdict(int)
    word_platforms = defaultdict(lambda: {'X': 0, 'YouTube': 0})
    
    # 【追加】スパム検知用の正規表現
    spam_pattern = re.compile(r'アマギフ|プレゼント|フォロー|RT|抽選')
    valid_posts_count = 0
    
    for _, row in df_raw.iterrows():
        text = row['text']
        
        # --- スパムフィルター ---
        if spam_pattern.search(text):
            continue # スパムと判定されたら集計せずにスキップ
            
        valid_posts_count += 1
        tokens = extract_tokens(text)
        for w in tokens:
            word_counts[w] += 1
            word_eng[w] += row['eng']
            word_platforms[w][row['platform']] += 1
            
        for w1, w2 in combinations(sorted(tokens), 2):
            pair_counts[(w1, w2)] += 1

    # (以下、グラフ構築処理は変更なし。ただし total_posts は valid_posts_count に変更)
    G = nx.Graph()
    for (w1, w2), count in pair_counts.items():
        if count >= 3:
            p_x = word_counts[w1] / valid_posts_count
            p_y = word_counts[w2] / valid_posts_count
            p_xy = count / valid_posts_count
            
            pmi = math.log10(p_xy / (p_x * p_y))
            npmi = pmi / -math.log10(p_xy)
            if npmi > 0.1:
                G.add_edge(w1, w2, weight=npmi, distance=1.0/npmi)

    k_val = min(50, len(G.nodes))
    betweenness = nx.betweenness_centrality(G, k=k_val, weight='distance') if len(G) > 0 else {}
    
    degree_centrality = {}
    for node in G.nodes:
        degree_centrality[node] = sum(data['weight'] for _, _, data in G.edges(node, data=True))

    unique_tokens = list(word_counts.keys())
    hist_db = get_historical_metrics(unique_tokens)

    features = []
    for w in unique_tokens:
        if word_counts[w] < 5: continue
        
        fx = word_platforms[w]['X']
        fyt = word_platforms[w]['YouTube']
        cross_platform_raw = (2 * min(fx, fyt)) / (fx + fyt + 1)
        
        max_conversion = 0.0
        for mw in MAGIC_WORDS:
            if G.has_edge(w, mw):
                max_conversion = max(max_conversion, G[w][mw]['weight'])
                
        hist = hist_db.get(w, {})
        freq_past = hist.get('freq_past', 0)
        freq_14d = hist.get('freq_14d', 0)
        
        features.append({
            'token': w,
            'freq_raw': word_counts[w],
            'growth_raw': (word_counts[w] + 5) / (freq_past + 5),
            'centrality_raw': degree_centrality.get(w, 0.0),
            'engagement_raw': word_eng[w] / word_counts[w],
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
