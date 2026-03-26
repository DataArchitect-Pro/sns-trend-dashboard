import streamlit as st
import pandas as pd
import plotly.express as px
from logic import run_pipeline

st.set_page_config(page_title="SNS Trend Analyzer", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. ヘッダー（価値と出力の2層構造）
# ==========================================
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")
st.markdown("""
**急上昇ワードの関連語を可視化し、次に狙う投稿テーマを抽出します。** 「今強い話題」と「次に来る切り口」を分けて分析し、解説型・比較型などの投稿案まで生成します。
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
# 3. サイドバー（STEP化と安心設計）
# ==========================================
with st.sidebar:
    st.header("STEP 1: データ読み込み")
    st.markdown("CSVを選択すると自動で分析を開始します。")
    uploaded_file = st.file_uploader("投稿CSVをアップロード", type=["csv"], label_visibility="collapsed")
    
    # セキュリティ文言をアップロード直下に配置し、コントラストを調整
    st.markdown("<span style='color: #666; font-size: 0.85em;'>🔒 データはこのセッション内でのみ処理され、保存されません。</span>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**▼ お試し用データ**")
    st.download_button(
        label="サンプルCSVをダウンロード",
        data=SAMPLE_CSV,
        file_name="sample_sns_data.csv",
        mime="text/csv",
        help="フォーマットの確認や、お試し分析にご利用ください。"
    )

    st.markdown("---")
    st.header("STEP 2: 分析設定")
    
    target_platforms = st.multiselect(
        "分析対象プラットフォーム",
        ["X", "YouTube", "Instagram", "TikTok"],
        default=["X", "YouTube"]
    )
    
    # 用語と補足をユーザーフレンドリーに修正
    min_freq = st.slider(
        "分析対象に含める最低出現回数", 
        min_value=1, max_value=20, value=3, 
        help="出現回数が少なすぎる語を除外して、ノイズを減らします。"
    )
    
    time_window = st.selectbox(
        "時系列比較の単位", 
        ["時間単位", "日単位", "週単位"], 
        index=1,
        help="時間単位: 短期バズの変化を細かく見ます / 日単位: 話題の勢い変化を日ごとに比較します / 週単位: 継続的に伸びるテーマを見ます"
    )
    
    st.markdown("---")
    st.header("🛡️ ノイズ制御")
    # ネガティブな印象を拭い、監査ツールとしての見せ方に変更
    show_noise = st.checkbox("ノイズ・スパム判定語を表示する", value=False, help="ツールが除外対象とした単語を確認したい場合にオンにしてください。")
    weight_eng = st.checkbox("エンゲージメント(熱量)を重視する", value=True)

# ==========================================
# 4. メイン画面（アップロード前：成果訴求と信頼感）
# ==========================================
if uploaded_file is None:
    # 行動を強制するCTA
    st.info("💡 **まずはCSVをアップロードして、トレンド分析を開始してください。** \n読み込み後すぐに、関連語・注目テーマ・投稿企画候補を生成します。")
    
    # 分析の信頼感を高めるロジックの提示
    st.markdown("<span style='color: #555; font-size: 0.9em;'>※ 投稿本文・投稿日時・媒体・エンゲージメントからスコアを算出します。単なる出現頻度だけでなく、**成長率・関連語ネットワークの構造・媒体横断性**も考慮して独自に分析します。</span>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_req, col_prev = st.columns([1, 1.2], gap="large")
    
    with col_req:
        st.subheader("📊 CSVの対応カラム")
        st.markdown("以下の列名を含めてアップロードしてください。（列の順序は問いません）")
        
        st.markdown("**【必須】**")
        st.markdown("- `text` : 投稿本文")
        
        st.markdown("**【推奨】**")
        st.markdown("- `posted_at` : 投稿日時")
        st.markdown("- `platform` : 媒体名（X / YouTubeなど）")
        st.markdown("- `eng` : エンゲージメント数")
        
        st.markdown("**【任意】**")
        st.markdown("- `id` : 投稿ID / `hashtags` : ハッシュタグ / `title` : タイトル")

    with col_prev:
        st.subheader("✨ 分析結果で分かること")
        # 具体例を混ぜて期待値をコントロール
        st.markdown("""
        <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 16px; background-color: #f9f9fc;">
            <strong>🔥 今強いキーワード</strong><br>
            <span style="font-size: 0.9em; color: #555;">圧倒的な話題量と熱量を持つトレンド語。</span><br>
            <span style="font-size: 0.85em; color: #0066cc;">例：生成AI / Python / トレンド</span><br><br>
            
            <strong>🌱 次に来そうなワード</strong><br>
            <span style="font-size: 0.9em; color: #555;">局地的に急成長しているブルーオーシャン。</span><br>
            <span style="font-size: 0.85em; color: #0066cc;">例：NanoBanana / Dify / RAG</span><br><br>
            
            <strong>💡 推奨投稿タイプとタイトル案</strong><br>
            <span style="font-size: 0.9em; color: #555;">関連語の構造から、最適な企画切り口を提案。</span><br>
            <span style="font-size: 0.85em; color: #0066cc;">例：【徹底比較】〇〇と△△の違い (比較型) / 今さら聞けない〇〇 (解説型)</span>
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

if 'eng' not in df_raw.columns: df_raw['eng'] = 0
if 'platform' not in df_raw.columns: df_raw['platform'] = 'X'

df_raw = df_raw[df_raw['platform'].isin(target_platforms)]

if df_raw.empty:
    st.warning("⚠️ 選択されたプラットフォームのデータが存在しません。サイドバーの分析設定を見直してください。")
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
