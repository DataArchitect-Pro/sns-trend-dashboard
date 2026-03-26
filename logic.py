import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler, MinMaxScaler

def create_dummy_data() -> pd.DataFrame:
    """Streamlit動作確認用のダミーデータ（10件）"""
    data = [
        {"token": "通常ワードA", "freq_raw": 10, "growth_raw": 1.2, "centrality_raw": 0.5, "engagement_raw": 5.0, "bridge_raw": 0.2, "cross_platform_raw": 0.5, "sustainability_raw": 0.8, "noise_risk_raw": 0.1, "novelty_raw": 0.3, "conversion_raw": 0.1},
        {"token": "次に来るワードB", "freq_raw": 50, "growth_raw": 15.0, "centrality_raw": 2.1, "engagement_raw": 12.0, "bridge_raw": 0.9, "cross_platform_raw": 0.8, "sustainability_raw": 0.2, "noise_risk_raw": 0.0, "novelty_raw": 0.9, "conversion_raw": 0.8},
        {"token": "覇権アニメC", "freq_raw": 50000, "growth_raw": 0.9, "centrality_raw": 5.5, "engagement_raw": 80.0, "bridge_raw": 0.1, "cross_platform_raw": 1.0, "sustainability_raw": 1.0, "noise_risk_raw": 0.2, "novelty_raw": 0.0, "conversion_raw": -0.2},
        {"token": "スパムBot群D", "freq_raw": 1000000, "growth_raw": 500.0, "centrality_raw": 0.0, "engagement_raw": 0.0, "bridge_raw": 0.0, "cross_platform_raw": 0.0, "sustainability_raw": 0.1, "noise_risk_raw": 1.0, "novelty_raw": 0.0, "conversion_raw": -0.9},
        {"token": "完全新規E", "freq_raw": 3, "growth_raw": np.nan, "centrality_raw": np.nan, "engagement_raw": np.nan, "bridge_raw": np.nan, "cross_platform_raw": np.nan, "sustainability_raw": np.nan, "noise_risk_raw": np.nan, "novelty_raw": np.nan, "conversion_raw": np.nan},
        {"token": "プチ炎上F", "freq_raw": 8000, "growth_raw": 20.0, "centrality_raw": 1.2, "engagement_raw": 45.0, "bridge_raw": 0.4, "cross_platform_raw": 0.2, "sustainability_raw": 0.1, "noise_risk_raw": 0.1, "novelty_raw": 0.7, "conversion_raw": 0.5},
        {"token": "ニッチ技術G", "freq_raw": 15, "growth_raw": 3.5, "centrality_raw": 0.8, "engagement_raw": 3.0, "bridge_raw": 0.7, "cross_platform_raw": 0.9, "sustainability_raw": 0.4, "noise_risk_raw": 0.0, "novelty_raw": 0.8, "conversion_raw": 0.9},
        {"token": "日常語H", "freq_raw": 500, "growth_raw": 1.0, "centrality_raw": 0.1, "engagement_raw": 1.0, "bridge_raw": 0.1, "cross_platform_raw": 0.5, "sustainability_raw": 1.0, "noise_risk_raw": 0.9, "novelty_raw": 0.0, "conversion_raw": 0.0},
    ]
    return pd.DataFrame(data)

def standardize_features(df_features: pd.DataFrame) -> pd.DataFrame:
    """検証済みの堅牢なスケーリング処理"""
    df = df_features.copy()
    
    # 対数化 (外れ値対策)
    df['freq_log'] = np.log1p(df['freq_raw'].fillna(0))
    df['engagement_log'] = np.log1p(df['engagement_raw'].fillna(0))
    
    target_cols = ['freq_log', 'growth_raw', 'centrality_raw', 'engagement_log']
    robust = RobustScaler()
    minmax = MinMaxScaler(feature_range=(0, 1))
    
    for col in target_cols:
        vals = df[[col]].fillna(0).values
        robust_vals = robust.fit_transform(vals)
        robust_vals_clipped = np.clip(robust_vals, a_min=None, a_max=3.0) # ハードクリップ
        
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
    """CSSとEOSの算出"""
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
    """ルールベースでのフラグとテキスト生成"""
    df['is_noise'] = df['noise_risk_z'] >= 0.8
    df['is_high_css'] = (df['score_css'] >= 60) & (~df['is_noise'])
    df['is_high_eos'] = (df['score_eos'] >= 60) & (~df['is_noise'])
    df['is_explainer'] = df['conversion_z'] >= 0.7
    df['is_comparative'] = df['bridge_z'] >= 0.6

    def generate_text(row):
        kw = row['token']
        if row['is_noise']:
            return "見送り", ""
        if row['is_high_css'] and row['is_explainer']:
            return "解説型", f"🚨【急上昇】今さら聞けない「{kw}」とは？3分で解説"
        elif row['is_high_eos'] and row['novelty_z'] >= 0.6:
            return "先読み型", f"💡【次に来る】そろそろ知っておきたい「{kw}」の始め方"
        elif row['is_comparative']:
            return "比較型", f"📊【徹底比較】「{kw}」と競合の違いまとめ"
        elif row['is_high_css']:
            return "まとめ型", f"📝【まとめ】バズり中の「{kw}」、みんなの反応一覧"
        elif row['is_high_eos']:
            return "注目型", f"🔍【注目】局地的に話題の「{kw}」をチェック"
        return "見送り", ""

    df[['text_content_type', 'text_title_seed']] = df.apply(
        lambda r: pd.Series(generate_text(r)), axis=1
    )
    return df

def run_pipeline() -> pd.DataFrame:
    """ダミーデータから最終出力までを一気通貫で実行"""
    df_raw = create_dummy_data()
    df_z = standardize_features(df_raw)
    df_scored = compute_scores(df_z)
    df_final = apply_decision_rules(df_scored)
    return df_final