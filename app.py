import streamlit as st
import pandas as pd
import plotly.express as px
from logic import run_pipeline

st.set_page_config(page_title="SNS Trend Analyzer", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. ヘッダー（成果訴求）
# ==========================================
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")
st.markdown("""
**急上昇ワードの関連語を可視化し、次に狙うべき投稿テーマを抽出します。** トレンド構造の分析から、「今強い話題」と「次に来る切り口」を分け、解説・比較・初心者向けなどの投稿企画案まで自動生成します。
""")

# ==========================================
# 2. サンプルデータの用意
# ==========================================
SAMPLE_CSV = """text,posted_at,platform,eng,id
新しい画像生成AIのNanoBananaとは？始め方を解説。,2023-10-01 10:00:00,X,25,A01
PythonとJavaScriptの違いを比較。初心者におすすめです。,2023-10-01 11:00:00,YouTube,40,B01
覇権アニメの最新話、最高だった。伏線の理由を考察してみた。,2023-10-01 12:00:00,X,150,C01
アマギフプレゼント！フォローとRTをお願いします！,2023-10-01 13:00:00,X,0,E01
今日の仕事疲れた。帰宅します。,2023-10-01 14:00:00,X,2,F01
"""

# ==========================================
# 3. サイドバー（設定・安心設計）
# ==========================================
with st.sidebar:
    st.header("📁 データ読み込み")
    uploaded_file = st.file_uploader("投稿CSVをアップロード", type=["csv"], help="最大50MB程度までを推奨します")
    
    st.markdown("---")
    st.header("📥 お試し用サンプル")
    st.download_button(
        label="サンプルCSVをダウンロード",
        data=SAMPLE_CSV,
        file_name="sample_sns_data.csv",
        mime="text/csv",
        help="フォーマットの確認や、お試し分析にご利用ください。"
    )

    st.markdown("---")
    st.header("⚙️ 分析設定")
    # UIとしての設定拡充（※本番ではlogic.pyと連動させます）
    target_platforms = st.multiselect(
        "分析対象プラットフォーム",
        ["X", "YouTube", "Instagram", "TikTok"],
        default=["X", "YouTube"]
    )
    min_freq = st.slider("最小出現頻度（足切りライン）", min_value=1, max_value=20, value=3, help="この回数未満しか出現しない単語は分析から除外します。")
    time_window = st.selectbox("時系列の比較粒度", ["時間単位", "日単位", "週単位"], index=1)
    
    st.markdown("---")
    st.header("🛡️ ノイズ制御")
    show_noise = st.checkbox("ノイズ・スパム語も結果に表示する", value=False)
    weight_eng = st.checkbox("エンゲージメント(熱量)を重視する", value=True)

# ==========================================
# 4. メイン画面（アップロード前：期待感と安心感の醸成）
# ==========================================
if uploaded_file is None:
    st.info("💡 **まずは投稿CSVを読み込み、関連語・注目テーマ・投稿企画候補の生成を開始してください。**")
    
    col_req, col_prev = st.columns([1, 1.2], gap="large")
    
    with col_req:
        st.subheader("📊 CSVの対応カラム（列）")
        st.markdown("以下の列名を含めてアップロードしてください。（※列の順序は問いません）")
        
        st.markdown("**【必須】**")
        st.markdown("- `text` : **投稿本文**（分析のコアデータです）")
        
        st.markdown("**【推奨】**（精度が向上します）")
        st.markdown("- `posted_at` : **投稿日時**（トレンドの「勢い」を判定します）")
        st.markdown("- `platform` : **媒体名** [X / YouTube]（媒体間の横断性を判定します）")
        st.markdown("- `eng` : **エンゲージメント数**（いいねやRT数。スパムの排除に役立ちます）")
        
        st.markdown("**【任意】**")
        st.markdown("- `id` : **投稿ID** / `hashtags` : **ハッシュタグ** / `url` : **投稿URL**")

        st.caption("🔒 **セキュリティについて:** アップロードされたデータはお使いのブラウザ・セッション内でのみ処理され、サーバー等に保存されることはありません。")

    with col_prev:
        st.subheader("✨ 分析結果で分かること（出力プレビュー）")
        st.markdown("""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; background-color: #f9f9fc;">
            <strong>🔥 今強いキーワード (Current Strength)</strong><br>
            <span style="font-size: 0.9em; color: #555;">圧倒的な話題量と熱量を持つ、今すぐ便乗すべきトレンド語。</span><br><br>
            <strong>🌱 次に来そうなワード (Emerging Opportunity)</strong><br>
            <span style="font-size: 0.9em; color: #555;">まだ絶対量は少ないが、局地的に急成長しているブルーオーシャン。</span><br><br>
            <strong>🕸️ 関連語ネットワーク・橋渡し語</strong><br>
            <span style="font-size: 0.9em; color: #555;">「A」と「B」の違いなど、意外な文脈を繋ぐキーワードの発見。</span><br><br>
            <strong>💡 おすすめ投稿タイプとタイトル案</strong><br>
            <span style="font-size: 0.9em; color: #555;">分析結果をもとに、「解説型」「比較型」などの企画案を自動生成。</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.stop()

# ==========================================
# 5. データ読み込みと前処理
# ==========================================
try:
    df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
except UnicodeDecodeError:
    df_raw = pd.read_csv(uploaded_file, encoding='cp932')

if 'text' not in df_raw.columns:
    st.error("❌ **エラー:** CSVファイルに必須カラム `text`（投稿本文）が見つかりません。列名をご確認の上、再度アップロードしてください。")
    st.stop()

# 欠損カラムの自動補完（エラーで落ちないための安心設計）
if 'eng' not in df_raw.columns: df_raw['eng'] = 0
if 'platform' not in df_raw.columns: df_raw['platform'] = 'X'

# UIのフィルタリングをデータに反映 (プラットフォーム絞り込み)
df_raw = df_raw[df_raw['platform'].isin(target_platforms)]

if df_raw.empty:
    st.warning("⚠️ 選択されたプラットフォームのデータが存在しません。サイドバーのフィルタ設定を見直してください。")
    st.stop()

# ==========================================
# 6. 分析パイプラインの実行
# ==========================================
with st.spinner("AIがトレンド構造を分析し、投稿企画案を生成しています..."):
    df = run_pipeline(df_raw)

if df.empty:
    st.warning("⚠️ 有効なトレンドキーワードが抽出できませんでした。データ量を増やすか、テキスト内容をご確認ください。")
    st.stop()

# ==========================================
# 7. 分析結果 UI 描画
# ==========================================
df_display = df if show_noise else df[~df['is_noise']].copy()

st.success("✅ 分析が完了しました！以下の企画案とトレンドマップをご確認ください。")

st.subheader("💡 抽出された投稿企画案 TOP3")
st.markdown("スコアと関連語の構造から、今作るべきコンテンツの切り口を提案します。")
ideas_df = df_display[df_display['text_content_type'] != "見送り"].sort_values(by='score_eos', ascending=False).head(3)

if not ideas_df.empty:
    cols = st.columns(len(ideas_df))
    for i, (_, row) in enumerate(ideas_df.iterrows()):
        with cols[i]:
            st.info(f"**{row['text_content_type']}**\n\n{row['text_title_seed']}")
            st.caption(f"話題力 (今): {row['score_css']} / ポテンシャル (次): {row['score_eos']}")
else:
    st.write("現在、強い推奨案はありません。")

st.divider()

st.subheader("📊 トレンド四象限マップ")
st.markdown("※左上の **「ポテンシャルが高く、話題力がまだ低いゾーン（ブルーオーシャン）」** が仕込みの狙い目です。")
fig = px.scatter(
    df_display, x="score_css", y="score_eos", text="token", size="freq_raw", color="text_content_type",
    hover_data=["freq_raw", "score_css", "score_eos"],
    labels={"score_css": "話題力 (Current Strength)", "score_eos": "ポテンシャル (Emerging Opportunity)", "text_content_type": "推奨投稿型"},
    height=550
)
fig.update_traces(textposition='top center')
fig.add_hline(y=50, line_dash="dot", line_color="gray")
fig.add_vline(x=50, line_dash="dot", line_color="gray")
fig.update_layout(xaxis_range=[0, 105], yaxis_range=[0, 105], margin=dict(t=20, b=20, l=20, r=20))
st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("📋 分析キーワード一覧")
view_cols = {
    'token': 'キーワード', 
    'text_content_type': '推奨投稿型', 
    'score_css': '話題力(CSS)', 
    'score_eos': 'ポテンシャル(EOS)', 
    'freq_raw': '出現回数', 
    'growth_raw': '成長率'
}
st.dataframe(
    df_display[list(view_cols.keys())].rename(columns=view_cols).sort_values(by='ポテンシャル(EOS)', ascending=False),
    use_container_width=True, hide_index=True
)
