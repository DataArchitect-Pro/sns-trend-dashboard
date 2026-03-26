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
    'こと', 'もの', 'これ', 'それ', 'あれ', '今日', '明日', '昨日', 'さん', 'ちゃん', 'くん', 
    'ため', 'よう', 'ところ', 'マジ', 'の', 'ん', 'お願い', '動画', '最新', '話', 'みんな', 
    '反応', '一覧', '最高', '普通', '日記', 'おすすめ', 'すごい', 'やばい', '便利', '私', '俺', 
    '僕', '自分', '人', '方', '何', '事', '時', '中', '前', '後', '気', '感', '感じ', 'みたい',
    'やつ', 'とき', 'そう', 'わけ', '内容', '情報', '結果', '発表', '本当', '今期', '最近', '今回'
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
        pos = token.part_of_speech.split(',')
        if pos[0] == '名詞' and pos[1] not in ['代名詞', '非自立', '数']:
            current_compound += token.surface
        else:
            if current_compound:
                if len(current_compound) > 1 and current_compound not in STOP_WORDS and not re.fullmatch(r'[ぁ-ん]{1,2}', current_compound):
                    tokens.append(current_compound)
                current_compound = ""
    if current_compound:
        if len(current_compound) > 1 and current_compound not in STOP_WORDS and not re.fullmatch(r'[ぁ-ん]{1,2}', current_compound):
            tokens.append(current_compound)
    return list(set(tokens))

def compute_network_and_features(df_raw: pd.DataFrame, min_freq: int) -> tuple[pd.DataFrame, dict]:
    if 'posted_at' in df_raw.columns:
        df_raw['posted_at'] = pd.to_datetime(df_raw['posted_at'], errors='coerce')
        
    word_counts = defaultdict(int)
    pair_counts = defaultdict(int)
    word_eng = defaultdict(int)
    word_platforms = defaultdict(lambda: {'X': 0, 'YouTube': 0})
    word_timestamps = defaultdict(list)
    
    spam_pattern = re.compile(r'アマギフ|プレゼント|フォロー|RT|抽選')
    valid_posts_count = 0
    
    for _, row in df_raw.iterrows():
        text = str(row.get('text', ''))
        if spam_pattern.search(text): continue
            
        valid_posts_count += 1
        eng_score = row.get('eng', 0)
        platform = row.get('platform', 'X')
        posted_at = row.get('posted_at')
        
        tokens = extract_tokens(text)
        for w in tokens:
            word_counts[w] += 1
            word_eng[w] += eng_score
            word_platforms[w][platform] += 1
            if pd.notnull(posted_at):
                word_timestamps[w].append(posted_at)
            
        for w1, w2 in combinations(sorted(tokens), 2):
            pair_counts[(w1, w2)] += 1

    unique_tokens = list(word_counts.keys())
    passed_tokens = [w for w in unique_tokens if word_counts[w] >= min_freq]
    dropped_tokens = [w for w in unique_tokens if word_counts[w] < min_freq]
    
    # 💡 条件未達の主因を1つに絞って明示的に定義する
    if valid_posts_count < min_freq:
        drop_reason = "投稿数不足"
    elif len(unique_tokens) == 0:
        drop_reason = "一般語過多"
    elif len(passed_tokens) == 0:
        drop_reason = "出現回数不足"
    else:
        drop_reason = "関連性の不足"

    metadata = {
        "valid_posts_count": valid_posts_count,
        "spam_dropped_count": len(df_raw) - valid_posts_count,
        "extracted_words_count": len(unique_tokens),
        "passed_words_count": len(passed_tokens),
        "dropped_tokens": dropped_tokens,
        "drop_reason": drop_reason
    }

    if not passed_tokens: return pd.DataFrame(), metadata

    G = nx.Graph()
    pair_min = max(2, min_freq - 1)
    for (w1, w2), count in pair_counts.items():
        if w1 not in passed_tokens or w2 not in passed_tokens: continue
        if count >= pair_min: 
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
        x_ratio_raw = fx / max(1, fx + fyt)
        
        max_conversion = 0.0
        for mw in MAGIC_WORDS:
            if G.has_edge(w, mw):
                max_conversion = max(max_conversion, G[w][mw]['weight'])
                
        timestamps = word_timestamps[w]
        duration_hours = 0.0
        if len(timestamps) > 1:
            duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0
            
        sustainability_raw = min(1.0, duration_hours / 72.0) if duration_hours > 0 else 0.0
        
        total_eng = word_eng[w]
        novelty_raw = max(0.0, 1.0 - (total_eng / 800.0))
        
        features.append({
            'token': w,
            'freq_raw': word_counts[w],
            'growth_raw': word_counts[w], 
            'centrality_raw': degree_centrality.get(w, 0.0),
            'engagement_raw': word_eng[w] / max(1, word_counts[w]),
            'bridge_raw': betweenness.get(w, 0.0),
            'cross_platform_raw': cross_platform_raw,
            'x_ratio_raw': x_ratio_raw,
            'sustainability_raw': sustainability_raw,
            'novelty_raw': novelty_raw,
            'conversion_raw': max_conversion,
            'duration_hours': duration_hours
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
        if len(vals) == 1:
            df[col.replace('_raw', '_z').replace('_log', '_z')] = np.array([1.0]) if vals[0][0] > 0 else np.array([0.0])
        else:
            robust_vals = robust.fit_transform(vals)
            robust_vals_clipped = np.clip(robust_vals, a_min=None, a_max=3.0)
            if robust_vals_clipped.max() == robust_vals_clipped.min():
                df[col.replace('_raw', '_z').replace('_log', '_z')] = np.ones_like(robust_vals_clipped).flatten() if vals[0][0] > 0 else np.zeros_like(robust_vals_clipped).flatten()
            else:
                df[col.replace('_raw', '_z').replace('_log', '_z')] = minmax.fit_transform(robust_vals_clipped).flatten()

    bridge_vals = df[['bridge_raw']].fillna(0).values
    if len(bridge_vals) == 1:
        df['bridge_z'] = np.array([1.0]) if bridge_vals[0][0] > 0 else np.array([0.0])
    else:
        if bridge_vals.max() == bridge_vals.min():
            df['bridge_z'] = np.ones_like(bridge_vals).flatten() if bridge_vals[0][0] > 0 else np.zeros_like(bridge_vals).flatten()
        else:
            df['bridge_z'] = minmax.fit_transform(bridge_vals).flatten()
    
    for col in ['cross_platform', 'sustainability', 'novelty', 'conversion']:
        df[f'{col}_z'] = df[f'{col}_raw'].fillna(0).clip(0, 1)
        
    df['x_ratio'] = df['x_ratio_raw']
        
    return df

def compute_scores(df_z: pd.DataFrame) -> pd.DataFrame:
    if df_z.empty: return df_z
    df = df_z.copy()
    
    df['score_css'] = (
        0.25 * df['freq_z'] + 0.20 * df['engagement_z'] + 0.15 * df['sustainability_z'] +
        0.20 * df['centrality_z'] + 0.10 * df['growth_z'] + 0.10 * df['cross_platform_z']
    ) * 100

    yt_bonus = (df['x_ratio'] < 0.3).astype(float) * 10.0

    df['score_eos'] = (
        0.25 * df['growth_z'] + 0.25 * df['sustainability_z'] + 0.20 * df['novelty_z'] +
        0.15 * df['bridge_z'] + 0.10 * df['conversion_z'] + 0.05 * df['cross_platform_z']
    ) * 100 + yt_bonus

    df['score_css'] = df['score_css'].clip(0, 100).round(1)
    df['score_eos'] = df['score_eos'].clip(0, 100).round(1)
    return df

def apply_decision_rules(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty: return df
    df['is_high_css'] = df['score_css'] >= 40
    df['is_high_eos'] = df['score_eos'] >= 50
    df['is_saturated'] = df['novelty_z'] < 0.3

    def generate_text(row):
        kw = row['token']
        x_ratio = row.get('x_ratio', 0.5)
        cross = row.get('cross_platform_z', 0.0)
        is_saturated = row.get('is_saturated', False)
        is_continuous = row.get('sustainability_z', 0.0) >= 0.7 and row.get('growth_z', 0.0) >= 0.5
        is_spike = row.get('duration_hours', 1.0) < 1.0 
        novelty = row.get('novelty_z', 0.0)

        if kw in MAGIC_WORDS: return "見送り", ""
        
        is_cross = cross >= 0.5 or (0.3 <= x_ratio <= 0.7)
        is_yt_heavy = x_ratio < 0.3
        is_x_heavy = x_ratio > 0.7
        
        if is_spike:
            if novelty >= 0.5: return "速報型", f"【速報】話題急騰中の「{kw}」まとめ"
            else: return "反応まとめ型", f"【局地的バズ】「{kw}」に対するみんなの反応"

        if is_saturated and not is_continuous:
            if row['bridge_z'] >= 0.2: return "比較型", f"【徹底比較】「{kw}」と競合の違いまとめ"
            elif is_yt_heavy or row['conversion_z'] >= 0.2: return "解説型", f"【最新版】「{kw}」の活用法まとめ"
            else: return "反応まとめ型", f"【みんなの反応】「{kw}」に対する活用事例"
            
        if is_cross:
            if row['bridge_z'] >= 0.2: return "比較型", f"【徹底比較】「{kw}」と競合の違いまとめ"
            elif row['is_high_eos']: return "先読み型", f"【次に来る】そろそろ知っておきたい「{kw}」"
            else: return "網羅まとめ型", f"【完全網羅】話題の「{kw}」に関する全情報"
        elif is_x_heavy:
            if novelty >= 0.5: return "先読み型", f"【次に来る】Xで密かに話題の「{kw}」とは？"
            elif is_continuous: return "解説型", f"【解説】Xでじわじわ伸びている「{kw}」について"
            else: return "反応まとめ型", f"【Xで話題】「{kw}」に対するみんなの反応"
        elif is_yt_heavy:
            if novelty >= 0.5: return "解説型", f"【最新AI】噂の「{kw}」をわかりやすく解説"
            elif row['conversion_z'] >= 0.2 or row['is_high_css']: return "解説型", f"【分かりやすく解説】「{kw}」の基本と使い方"
            else: return "初心者向け", f"【初心者向け】噂の「{kw}」をゼロから解説"

        return "解説型", f"【解説】「{kw}」について"

    df[['text_content_type', 'text_title_seed']] = df.apply(lambda r: pd.Series(generate_text(r)), axis=1)
    return df

def run_pipeline(df_raw: pd.DataFrame, min_freq: int = 3) -> tuple[pd.DataFrame, dict]:
    if df_raw.empty: return pd.DataFrame(), {}
    df_features, metadata = compute_network_and_features(df_raw, min_freq)
    if df_features.empty: return pd.DataFrame(), metadata
    df_z = standardize_features(df_features)
    df_scored = compute_scores(df_z)
    df_final = apply_decision_rules(df_scored)
    return df_final, metadata
