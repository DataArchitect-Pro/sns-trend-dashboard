import pandas as pd
import numpy as np
import networkx as nx
import math
import re
from collections import defaultdict
from itertools import combinations
from sklearn.preprocessing import RobustScaler, MinMaxScaler
from janome.tokenizer import Tokenizer

tokenizer = Tokenizer()

STOP_WORDS = {
    'こと', 'もの', 'これ', 'それ', '今日', 'さん', 'ちゃん', 'ため', 'よう', 'ところ', 
    'マジ', 'の', 'ん', 'お願い', '動画', '最新', '話', 'みんな', '反応', '一覧', '最高'
}
MAGIC_WORDS = {'とは', '違い', 'おすすめ', '比較', '理由', 'メリット', 'デメリット', 'やり方', '始め方', '初心者', '解説', 'まとめ'}

def get_historical_metrics(tokens: list) -> dict:
    hist = {}
    for t in tokens:
        hist[t] = {'freq_past': 0, 'freq_14d': 0, 'days_7d': 1, 'days_30d': 1}
    return hist

def extract_tokens(text: str) -> list:
    tokens = []
    current_compound = ""
    for token in tokenizer.tokenize(str(text)):
        if token.part_of_speech.startswith('名詞'):
            current_compound += token.surface
        else:
            if current_compound:
                if len(current_compound) > 1 and current_compound not in STOP_WORDS:
                    tokens.append(current_compound)
                current_compound = ""
    if current_compound:
        if len(current_compound) > 1 and current_compound not in STOP_WORDS:
            tokens.append(current_compound)
    return list(set(tokens))

def compute_network_and_features(df_raw: pd.DataFrame, min_freq: int) -> tuple[pd.DataFrame, dict]:
    word_counts = defaultdict(int)
    pair_counts = defaultdict(int)
    word_eng = defaultdict(int)
    word_platforms = defaultdict(lambda: {'X': 0, 'YouTube': 0})
    
    spam_pattern = re.compile(r'アマギフ|プレゼント|フォロー|RT|抽選')
    valid_posts_count = 0
    
    for _, row in df_raw.iterrows():
        text = str(row.get('text', ''))
        if spam_pattern.search(text):
            continue
            
        valid_posts_count += 1
        eng_score = row.get('eng', 0)
        platform = row.get('platform', 'X')
        
        tokens = extract_tokens(text)
        for w in tokens:
            word_counts[w] += 1
            word_eng[w] += eng_score
            word_platforms[w][platform] += 1
            
        for w1, w2 in combinations(sorted(tokens), 2):
            pair_counts[(w1, w2)] += 1

    unique_tokens = list(word_counts.keys())
    # 設定された最低出現回数（min_freq）で足切り
    passed_tokens = [w for w in unique_tokens if word_counts[w] >= min_freq]
    
    # 失敗画面UIに渡すためのメタデータを作成
    metadata = {
        "valid_posts_count": valid_posts_count,
        "spam_dropped_count": len(df_raw) - valid_posts_count,
        "extracted_words_count": len(unique_tokens),
        "passed_words_count": len(passed_tokens),
    }

    if not passed_tokens:
        return pd.DataFrame(), metadata

    G = nx.Graph()
    for (w1, w2), count in pair_counts.items():
        if w1 not in passed_tokens or w2 not in passed_tokens:
            continue
        if count >= 3:
            p_x = word_counts[w1] / max(1, valid_posts_count)
            p_y = word_counts[w2] / max(1, valid_posts_count)
            p_xy = count / max(1, valid_posts_count)
            
            pmi = math.log10(p_xy / (p_x * p_y))
            npmi = pmi / -math.log10(p_xy)
            if npmi > 0.1:
                G.add_edge(w1, w2, weight=npmi, distance=1.0/npmi)

    k_val = min(50, len(G.nodes))
    betweenness = nx.betweenness_centrality(G, k=k_val, weight='distance') if len(G) > 0 else {}
    degree_centrality = {node: sum(data['weight'] for _, _, data in G.edges(node, data=True)) for node in G.nodes}

    hist_db = get_historical_metrics(unique_tokens)

    features = []
    for w in passed_tokens:
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
            'engagement_raw': word_eng[w] / max(1, word_counts[w]),
            'bridge_raw': betweenness.get(w, 0.0),
            'cross_platform_raw': cross_platform_raw,
            'sustainability_raw': hist.get('days_7d', 1) / 7.0,
            'noise_risk_raw': hist.get('days_30d', 1) / 30.0,
            'novelty_raw': max(0.0, 1.0 - (freq_14d / 100.0)),
            'conversion_raw': max_conversion
        })
        
    return pd.DataFrame(features), metadata

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
        df[col.replace('_raw', '_z').replace('_log', '_z')] = minmax.fit_transform(robust_vals_clipped)

    df['bridge_z'] = minmax.fit_transform(df[['bridge_raw']].fillna(0).values)
    
    for col in ['cross_platform', 'sustainability', 'noise_risk', 'novelty', 'conversion']:
        df[f'{col}_z'] = df[f'{col}_raw'].fillna(0).clip(0, 1)
        
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
    df['is_high_css'] = (df['score_css'] >= 40) & (~df['is_noise']) 
    df['is_high_eos'] = (df['score_eos'] >= 50) & (~df['is_noise'])
    df['is_explainer'] = df['conversion_z'] >= 0.3
    df['is_comparative'] = df['bridge_z'] >= 0.3

    def generate_text(row):
        kw = row['token']
        if row['is_noise'] or kw in MAGIC_WORDS:
            return "見送り", ""
        if row['is_comparative']:
            return "比較型", f"【徹底比較】「{kw}」と競合の違いまとめ"
        elif row['is_high_css'] and row['is_explainer']:
            return "解説型", f"【急上昇】今さら聞けない「{kw}」とは？"
        elif row['is_high_eos'] and row['novelty_z'] >= 0.5:
            return "先読み型", f"【次に来る】そろそろ知っておきたい「{kw}」"
        elif row['is_high_css']:
            return "まとめ型", f"【まとめ】バズり中の「{kw}」、みんなの反応"
        elif row['is_high_eos']:
            return "注目型", f"【注目】局地的に話題の「{kw}」をチェック"
        return "見送り", ""

    df[['text_content_type', 'text_title_seed']] = df.apply(lambda r: pd.Series(generate_text(r)), axis=1)
    return df

def run_pipeline(df_raw: pd.DataFrame, min_freq: int = 3) -> tuple[pd.DataFrame, dict]:
    if df_raw.empty:
        return pd.DataFrame(), {}
    # min_freqを引数として渡し、メタデータも受け取る
    df_features, metadata = compute_network_and_features(df_raw, min_freq)
    if df_features.empty:
        return pd.DataFrame(), metadata
    df_z = standardize_features(df_features)
    df_scored = compute_scores(df_z)
    df_final = apply_decision_rules(df_scored)
    return df_final, metadata
