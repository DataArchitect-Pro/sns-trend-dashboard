import streamlit as st
import plotly.express as px
from logic import run_pipeline

# ページ設定
st.set_page_config(page_title="SNS Trend & Keyword Analyzer", layout="wide")
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")
st.markdown("「今強いワード(CSS)」と「次に来るワード(EOS)」を可視化し、投稿企画案を自動提案します。")

# バックエンド処理の実行
@st.cache_data
def load_data():
    return run_pipeline()

df = load_data()

# サイドバー（フィルタ）
st.sidebar.header("⚙️ フィルタ設定")
show_noise = st.sidebar.checkbox("ノイズ・スパム語を表示する", value=False)

if not show_noise:
    df_display = df[~df['is_noise']].copy()
else:
    df_display = df.copy()

# -----------------------------------------
# 1. 投稿企画案 (Action Panel)
# -----------------------------------------
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

# -----------------------------------------
# 2. 四象限マトリクス (Scatter Plot)
# -----------------------------------------
st.subheader("📊 トレンド四象限マップ")
st.markdown("※左上（**ブルーオーシャン**）にあるワードが仕込みの狙い目です。")

fig = px.scatter(
    df_display,
    x="score_css", y="score_eos",
    text="token", size="freq_raw", color="text_content_type",
    hover_data=["freq_raw", "score_css", "score_eos"],
    labels={"score_css": "Current Strength (今の話題力)", "score_eos": "Emerging Opportunity (次に来るポテンシャル)"},
    height=500
)
fig.update_traces(textposition='top center')
fig.add_hline(y=60, line_dash="dot", line_color="gray")
fig.add_vline(x=60, line_dash="dot", line_color="gray")
fig.update_layout(xaxis_range=[0, 105], yaxis_range=[0, 105])

st.plotly_chart(fig, use_container_width=True)

st.divider()

# -----------------------------------------
# 3. データ詳細一覧
# -----------------------------------------
st.subheader("📋 分析結果一覧")
view_cols = ['token', 'text_content_type', 'score_css', 'score_eos', 'freq_raw', 'growth_raw', 'text_title_seed']
st.dataframe(
    df_display[view_cols].sort_values(by='score_eos', ascending=False),
    use_container_width=True,
    hide_index=True
)