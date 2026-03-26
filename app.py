import streamlit as st
import pandas as pd
import plotly.express as px
from logic import run_pipeline

st.set_page_config(page_title="SNS Trend Analyzer", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# 1. ヘッダー
# ==========================================
st.title("🎯 SNSトレンド・キーワード相関分析ダッシュボード")

st.markdown("**急上昇ワードの関連語を可視化し、次に狙う投稿テーマを抽出します。**")
st.markdown("「今強い話題」と「次に来る切り口」を分けて分析し、解説型・比較型などの投稿案まで生成します。")

st.markdown("""
<div style="color: #444; font-size: 0.95em; margin-top: 8px; margin-bottom: 16px;">
※ 投稿本文・日時・媒体・エンゲージメントからスコアを算出します。<br>
※ 出現頻度だけでなく、成長率・関連語構造・媒体横断性も考慮して独自に分析します。
</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. サンプルデータの用意 (リッチ版)
# ==========================================
SAMPLE_CSV = """text,posted_at,platform,eng,id
次世代の画像生成AI、NanoBananaとは？始め方を解説。,2023-10-01 10:00:00,X,50,A01
NanoBananaの始め方を初心者向けに解説します。,2023-10-01 10:15:00,YouTube,80,A02
画像生成AIのNanoBanana、プロンプトのコツと始め方。,2023-10-01 10:30:00,X,60,A03
画像生成AIのNanoBananaとは？他のAIとの違いを比較してみた。,2023-10-01 11:00:00,YouTube,120,A04
PythonとJavaScriptの違いを徹底比較！どっちを学ぶべき？,2023-10-01 11:30:00,YouTube,300,B01
初心者におすすめなのはPython？JavaScript？違いを解説。,2023-10-01 12:00:00,X,150,B02
Web開発ならJavaScript、AIならPython。それぞれのメリットを比較。,2023-10-01 12:30:00,X,180,B03
Pythonの学習ロードマップまとめ。初心者必見！,2023-10-01 13:00:00,YouTube,400,B04
今期の覇権アニメ、神作画すぎた。みんなの反応まとめ。,2023-10-01 13:30:00,X,1500,C01
覇権アニメ第8話の伏線考察まとめ！,2023-10-01 14:00:00,YouTube,2500,C02
覇権アニメの最新話、海外の反応まとめ動画です。,2023-10-01 14:30:00,YouTube,3000,C03
覇権アニメ、なぜここまで人気なのか？海外の反応と理由を解説。,2023-10-01 15:00:00,X,1200,C04
アマギフプレゼント！フォローとRTをお願いします！,2023-10-01 15:30:00,X,0,E01
抽選で最新ゲーム機プレゼント！RTとフォロー必須！,2023-10-01 16:00:00,X,0,E02
今日の仕事疲れたー。早く帰宅したい。,2023-10-01 16:30:00,X,5,F01
仕事終わらない。明日も仕事だ。,2023-10-01 17:00:00,X,2,F02
"""

# ==========================================
# 3. サイドバー
# ==========================================
with st.sidebar:
    st.header("STEP 1: データ読み込み")
    st.write("CSVを選択すると自動で分析を開始します。（上限200MB）")
    
    uploaded_file = st.file_uploader("CSVアップロード", type=["csv"], label_visibility="collapsed")
    st.markdown("<div style='color: #666; font-size: 0.8em; margin-top: -10px; margin-bottom: 10px;'>🔒 データはこのセッション内でのみ処理され、保存されません。</div>", unsafe_allow_html=True)
    
    st.download_button(
        label="📥 サンプルCSVをダウンロード",
        data=SAMPLE_CSV,
        file_name="sample_sns_data.csv",
        mime="text/csv",
        help="フォーマットの確認や、お試し分析にご利用ください。"
    )

    st.divider()

    st.header("STEP 2: 分析設定")
    target_platforms = st.multiselect(
        "分析対象プラットフォーム",
        ["X", "YouTube", "Instagram", "TikTok"],
        default=["X", "YouTube"]
    )
    
    min_freq = st.slider(
        "最低出現回数（ノイズ除外）", 
        min_value=1, max_value=20, value=3, 
        help="出現回数が少なすぎる語を除外して、ノイズを減らします。"
    )
    
    time_window = st.selectbox(
        "時系列比較の単位", 
        ["時間単位", "日単位", "週単位"], 
        index=1
    )
    
    st.divider()

    st.header("STEP 3: 表示オプション")
    show_noise = st.checkbox("ノイズ・スパム判定語を表示する", value=False)
    weight_eng = st.checkbox(
        "エンゲージメントをスコアに反映する", 
        value=True,
        help="反応数も加味して話題性を評価します。投稿本文だけで見たい場合はオフにしてください。"
    )

# ==========================================
# 4. メイン画面（アップロード前）
# ==========================================
if uploaded_file is None:
    st.info("💡 **まずはCSVをアップロードして、トレンド分析を開始してください。** \n読み込み後すぐに、関連語・注目テーマ・投稿企画候補を生成します。")
    st.write("") 
    
    col_req, col_prev = st.columns([1, 1], gap="large")
    
    with col_req:
        st.subheader("📊 CSVの対応カラム")
        st.write("以下の列名を含めてアップロードしてください。（列の順序は問いません）")
        
        st.markdown("""
        **<span style="color: #d32f2f;">【必須】</span>**
        * `text` : **投稿本文**（分析のコアデータ）
        
        **【推奨】**
        <div style="color: #444; font-size: 0.95em; margin-left: 20px;">
        • <code>posted_at</code> : 投稿日時（話題の勢いを判定）<br>
        • <code>platform</code> : 媒体名（媒体間の違いを比較）<br>
        • <code>eng</code> : エンゲージメント数（反応の強さを補正）
        </div>
        
        <br>**<span style="color: #888;">【任意】</span>**
        <div style="color: #888; font-size: 0.9em; margin-left: 20px;">
        • <code>hashtags</code> : ハッシュタグ / <code>id</code> : 投稿ID / <code>title</code> : タイトル
        </div>
        """, unsafe_allow_html=True)

    with col_prev:
        st.subheader("✨ 分析結果で分かること")
        with st.container(border=True):
            st.markdown("##### 🔥 今強いキーワード")
            st.markdown("`生成AI` `Python` `トレンド分析`")
            st.write("")
            st.markdown("##### 🌱 次に来そうなワード")
            st.markdown("`NanoBanana` `Dify` `RAG`")
            st.write("")
            st.markdown("##### 💡 おすすめ投稿タイプ")
            st.markdown("`比較型` `解説型` `先読み型`")
    
    st.divider()
    
    st.subheader("🚀 分析開始後の流れ")
    col_step1, col_step2, col_step3 = st.columns(3)
    with col_step1:
        st.info("**1. CSV読み込み**\n\nノイズを自動で除外し、不要な単語を整理します。")
    with col_step2:
        st.info("**2. キーワード分析**\n\n話題の強さや、単語間の関連構造を分析・スコア化します。")
    with col_step3:
        st.success("**3. 投稿案生成**\n\n分析結果に基づき、次に狙うべき投稿テーマを提案します。")

    st.stop()

# ==========================================
# 5. データ読み込みと実行
# ==========================================
try:
    df_raw = pd.read_csv(uploaded_file, encoding='utf-8')
except UnicodeDecodeError:
    df_raw = pd.read_csv(uploaded_file, encoding='cp932')

if 'text' not in df_raw.columns:
    st.error("❌ **エラー:** CSVファイルに必須カラム `text`（投稿本文）が見つかりません。")
    st.stop()

if 'eng' not in df_raw.columns: df_raw['eng'] = 0
if 'platform' not in df_raw.columns: df_raw['platform'] = 'X'
df_raw = df_raw[df_raw['platform'].isin(target_platforms)]

with st.spinner("AIがトレンド構造を分析し、投稿企画案を生成しています..."):
    df = run_pipeline(df_raw)

if df.empty:
    st.warning("⚠️ 有効なトレンドキーワードが抽出できませんでした。データ量を増やすか設定を見直してください。")
    st.stop()

# ==========================================
# 6. 結果の事後処理 (ランキング・理由の付与)
# ==========================================
df_display = df if show_noise else df[~df['is_noise']].copy()

# 提案可能な企画をポテンシャル順にソート
ideas_df = df_display[df_display['text_content_type'] != "見送り"].sort_values(by=['score_eos', 'score_css'], ascending=[False, False])

# TOP3に番号を付与
top3_indices = ideas_df.head(3).index
df_display['Rank_Num'] = ""
df_display['plot_label'] = df_display['token'] # マップ表示用ラベル

if len(top3_indices) > 0:
    df_display.loc[top3_indices[0], 'Rank_Num'] = "①"
    df_display.loc[top3_indices[0], 'plot_label'] = "① " + df_display.loc[top3_indices[0], 'token']
if len(top3_indices) > 1:
    df_display.loc[top3_indices[1], 'Rank_Num'] = "②"
    df_display.loc[top3_indices[1], 'plot_label'] = "② " + df_display.loc[top3_indices[1], 'token']
if len(top3_indices) > 2:
    df_display.loc[top3_indices[2], 'Rank_Num'] = "③"
    df_display.loc[top3_indices[2], 'plot_label'] = "③ " + df_display.loc[top3_indices[2], 'token']

# 推奨理由とアクションを自動生成
def enrich_card_data(row):
    if row['text_content_type'] == "先読み型":
        return "成長率が高く、まだ競合が少ないため", "情報感度高め層", "今すぐ仕込み投稿（ブルーオーシャン）"
    elif row['text_content_type'] == "解説型":
        return "話題性が急上昇しており、検索需要が高いため", "初心者・入門層", "図解・解説投稿を作成"
    elif row['text_content_type'] == "比較型":
        return "関連語との結びつきが強く、違いへの関心が高いため", "検討・比較層", "競合との違いを提示する"
    elif row['text_content_type'] == "まとめ型":
        return "圧倒的な話題量を持ち、反応が多いため", "一般大衆層", "反応や事例のまとめを作成"
    elif row['text_content_type'] == "注目型":
        return "局地的に強い反応が発生しているため", "ニッチ層", "関連動向の監視・速報"
    return "話題力・ポテンシャル共に低迷", "-", "見送り"

df_display[['reason', 'target', 'action']] = df_display.apply(lambda r: pd.Series(enrich_card_data(r)), axis=1)

# 行動一覧表用の優先度判定
def set_priority(row):
    if row['Rank_Num'] != "": return "🔥 S (最優先)"
    if row['score_eos'] >= 50: return "👀 A (監視・次点)"
    if row['score_css'] >= 50: return "📝 B (後追い)"
    return "➖ C (見送り)"

df_display['priority'] = df_display.apply(set_priority, axis=1)

# ==========================================
# 7. UI 描画 (結果画面)
# ==========================================
# 通知は控えめに
st.markdown("<div style='color: #2e7d32; font-weight: bold; margin-bottom: 20px;'>✅ 分析完了：今作るべき投稿企画とトレンドマップが生成されました。</div>", unsafe_allow_html=True)

# --- A. 企画案 TOP3 ---
st.subheader("🔥 今作るべき投稿企画 TOP3")

top3_ideas = df_display[df_display['Rank_Num'] != ""].sort_values(by='Rank_Num')

if not top3_ideas.empty:
    cols = st.columns(3)
    for i, (_, row) in enumerate(top3_ideas.iterrows()):
        with cols[i]:
            # カードの高さを揃え、視覚的階層を明確にする
            bg_color = "#fff8e1" if row['Rank_Num'] == "①" else "#ffffff"
            border_color = "#ffc107" if row['Rank_Num'] == "①" else "#e0e0e0"
            rank_badge = "👑 最優先" if row['Rank_Num'] == "①" else f"{row['Rank_Num']}位"
            
            st.markdown(f"""
            <div style="border: 2px solid {border_color}; border-radius: 8px; padding: 16px; background-color: {bg_color}; height: 260px;">
                <span style="background-color: #333; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 8px;">{row['text_content_type']}</span>
                <span style="font-weight: bold; color: #d32f2f;">{rank_badge}</span>
                <h4 style="margin-top: 12px; margin-bottom: 12px; font-size: 1.1em; line-height: 1.4;">{row['text_title_seed']}</h4>
                <div style="font-size: 0.85em; color: #444; line-height: 1.6;">
                    <b>理由：</b>{row['reason']}<br>
                    <b>対象：</b>{row['target']}<br>
                    <b>推奨アクション：</b><span style="color: #1976d2; font-weight: bold;">{row['action']}</span>
                </div>
                <div style="margin-top: 12px; font-size: 0.8em; color: #888;">
                    話題力: {row['score_css']} / ポテンシャル: {row['score_eos']}
                </div>
            </div>
            """, unsafe_allow_html=True)
else:
    st.write("現在、強い推奨案はありません。")

# 投稿型の解説アコーディオン
with st.expander("💡 各「投稿型」の意味と狙い"):
    st.markdown("""
    * **先読み型:** まだ競争が浅く、これから伸びるテーマ。いち早く発信することで第一人者ポジションを狙えます。
    * **解説型:** 今話題になり始めているテーマ。検索需要に応える図解や基本解説が刺さります。
    * **比較型:** 関連語との結びつきが強いテーマ。「AとBの違い」「どっちを選ぶべきか」のコンテンツが有効です。
    * **まとめ型:** すでに巨大なバズになっているテーマ。事例やみんなの反応をまとめた保存用のコンテンツが適しています。
    """)

st.divider()

# --- B. トレンドマップ ---
st.subheader("📊 トレンド四象限マップ")

col_map_desc, _ = st.columns([2, 1])
with col_map_desc:
    st.info("""
    **【マップの読み方】**
    * **左上 (先回り):** まだ競争が浅く、先回りしやすい仕込み候補（★狙い目）
    * **右上 (本命):** すでに注目度も高く、有力な本命テーマ
    * **右下 (後追い):** 話題にはなっているが、先行優位は薄い
    * **左下 (見送り):** 現時点では優先度低め
    """)

fig = px.scatter(
    df_display, x="score_css", y="score_eos", text="plot_label", size="freq_raw", color="text_content_type",
    hover_data=["freq_raw", "score_css", "score_eos"],
    labels={"score_css": "話題力 (Current Strength)", "score_eos": "ポテンシャル (Emerging Opportunity)", "text_content_type": "推奨投稿型", "plot_label": "キーワード"},
    height=600
)
fig.update_traces(textposition='top center', textfont_size=14) # 注釈文字を少し大きく
fig.add_hline(y=50, line_dash="dot", line_color="gray")
fig.add_vline(x=50, line_dash="dot", line_color="gray")
fig.update_layout(xaxis_range=[0, 105], yaxis_range=[0, 105], margin=dict(t=20, b=20, l=20, r=20))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- C. アクション一覧表 ---
st.subheader("📋 行動計画・キーワード一覧")
st.markdown("抽出された全キーワードの優先度と推奨アクションのリストです。")

view_cols = {
    'priority': '優先度',
    'token': 'キーワード', 
    'text_content_type': '推奨投稿型',
    'action': '推奨アクション',
    'reason': '判定理由',
    'score_css': '話題力(CSS)', 
    'score_eos': 'ポテンシャル(EOS)', 
}

st.dataframe(
    df_display[list(view_cols.keys())].rename(columns=view_cols).sort_values(by=['優先度', 'ポテンシャル(EOS)'], ascending=[True, False]),
    use_container_width=True, hide_index=True
)
