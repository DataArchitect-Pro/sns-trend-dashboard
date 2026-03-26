import streamlit as st
import plotly.express as px
from logic import run_pipeline, fetch_raw_posts

st.set_page_config(page_title="SNS Trend Analyzer", layout="wide")
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")
st.markdown("生の投稿テキストを形態素解析・ネットワーク分析し、投稿企画案を動的に生成しています。")

@st.cache_data
def load_data():
    raw_posts = fetch_raw_posts()
    final_df = run_pipeline()
    return raw_posts, final_df

df_raw, df = load_data()

st.sidebar.header("⚙️ フィルタ設定")
show_noise = st.sidebar.checkbox("ノイズ・スパム語を表示する", value=False)

st.sidebar.divider()
st.sidebar.subheader("📄 生データ確認 (裏側)")
st.sidebar.dataframe(df_raw[['platform', 'text', 'eng']].head(50), height=300)

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
