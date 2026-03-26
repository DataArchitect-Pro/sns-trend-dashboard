import streamlit as st
import pandas as pd
import plotly.express as px
from logic import run_pipeline

st.set_page_config(page_title="SNS Trend Analyzer", layout="wide")
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")
st.markdown("X(Twitter)やYouTubeの投稿CSVをアップロードすると、投稿企画案を自動生成します。")

# ==========================================
# サイドバー: ファイルアップロード設定
# ==========================================
st.sidebar.header("📁 データ読み込み")
uploaded_file = st.sidebar.file_uploader("投稿CSVをアップロード", type=["csv"])

st.sidebar.divider()
st.sidebar.header("⚙️ フィルタ設定")
show_noise = st.sidebar.checkbox("ノイズ・スパム語を表示する", value=False)

# ==========================================
# メイン処理
# ==========================================
if uploaded_file is None:
    # ファイルがない時の案内画面
    st.info("👈 左側のサイドバーから、投稿データ(CSV)をアップロードしてください。")
    st.markdown("""
    **【CSVに必要なカラム】**
    * `id` : 投稿ID（任意）
    * `platform` : X または YouTube（任意）
    * `text` : 投稿本文（**必須**）
    * `eng` : いいね・RTなどのエンゲージメント数（任意）
    """)
    st.stop()

# CSV読み込み（Excel特有の文字化けエラーを自動回避）
try:
    df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
except UnicodeDecodeError:
    df_raw = pd.read_csv(uploaded_file, encoding='cp932')

# 必須カラムチェック
if 'text' not in df_raw.columns:
    st.error("❌ エラー: CSVファイルに `text` カラムが見つかりません。投稿本文のカラム名を `text` に変更して再度アップロードしてください。")
    st.stop()

# 欠損カラムの自動補完
if 'eng' not in df_raw.columns:
    df_raw['eng'] = 0
if 'platform' not in df_raw.columns:
    df_raw['platform'] = 'X'

# 処理実行
with st.spinner("AIが形態素解析とネットワーク分析を実行中..."):
    df = run_pipeline(df_raw)

if df.empty:
    st.warning("有効なトレンドキーワードが抽出できませんでした。データ量を増やすか、テキスト内容をご確認ください。")
    st.stop()

# ==========================================
# UI 描画
# ==========================================
df_display = df if show_noise else df[~df['is_noise']].copy()

# 1. 投稿企画案
st.subheader("💡 今すぐ作るべき投稿企画案 TOP3")
ideas_df = df_display[df_display['text_content_type'] != "見送り"].sort_values(by='score_eos', ascending=False).head(3)

if not ideas_df.empty:
    cols = st.columns(len(ideas_df))
    for i, (_, row) in enumerate(ideas_df.iterrows()):
        with cols[i]:
            st.info(f"**{row['text_content_type']}**\n\n{row['text_title_seed']}")
            st.caption(f"CSS (今): {row['score_css']} / EOS (次): {row['score_eos']}")
else:
    st.write("現在、強い推奨案はありません。")

st.divider()

# 2. 四象限マトリクス
st.subheader("📊 トレンド四象限マップ")
fig = px.scatter(
    df_display, x="score_css", y="score_eos", text="token", size="freq_raw", color="text_content_type",
    hover_data=["freq_raw", "score_css", "score_eos"],
    labels={"score_css": "Current Strength (話題力)", "score_eos": "Emerging Opportunity (ポテンシャル)"},
    height=500
)
fig.update_traces(textposition='top center')
fig.add_hline(y=50, line_dash="dot", line_color="gray")
fig.add_vline(x=50, line_dash="dot", line_color="gray")
fig.update_layout(xaxis_range=[0, 105], yaxis_range=[0, 105])

st.plotly_chart(fig, use_container_width=True)

st.divider()

# 3. データ詳細一覧
st.subheader("📋 分析結果一覧")
view_cols = ['token', 'text_content_type', 'score_css', 'score_eos', 'freq_raw', 'growth_raw', 'bridge_raw', 'conversion_raw']
st.dataframe(
    df_display[view_cols].sort_values(by='score_eos', ascending=False),
    use_container_width=True, hide_index=True
)
