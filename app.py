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
<div style="color: #444; font-size: 0.9em; margin-top: 4px; margin-bottom: 8px;">
※ 投稿本文・日時・媒体・エンゲージメントからスコアを算出します。<br>
※ 出現頻度だけでなく、成長率・関連語構造・媒体横断性も考慮して独自に分析します。
</div>
""", unsafe_allow_html=True)

# ==========================================
# 2. サンプルデータの用意 (省略せずに記載)
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
    st.write("CSVを選択すると分析を開始します（上限200MB）")
    
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

    st.header("STEP 3: 分析オプション")
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
    df, metadata = run_pipeline(df_raw, min_freq=min_freq)

# ==========================================
# 🚨 失敗時のリカバリーUI
# ==========================================
if df.empty:
    st.markdown("<h3 style='color: #d32f2f;'>⚠️ 現在の条件では、有効なトレンド候補を判定できませんでした</h3>", unsafe_allow_html=True)
    st.markdown("現在のCSVでは、しきい値を満たすキーワードが見つかりませんでした。<br><span style='color: #666; font-size: 0.9em;'>原因候補：一般語の多さ / 投稿数不足 / しきい値未達</span>", unsafe_allow_html=True)
    
    st.write("") 
    col_err_left, col_err_right = st.columns([1, 1], gap="large")
    
    with col_err_left:
        drop_reason = metadata.get('drop_reason', '条件未達')
        if "出現回数不足" in drop_reason:
            main_cause = "出現回数不足"
            detail = f"抽出された候補語のうち、最低出現回数（{min_freq}回）を満たすものが0件でした。"
        elif "固有トピック" in drop_reason:
            main_cause = "固有トピックの不足"
            detail = "一般語やノイズが多く、分析対象となるキーワードが抽出されませんでした。"
        else:
            main_cause = "関連性の不足"
            detail = "キーワード同士の共起（一緒に呟かれること）が基準に満ちませんでした。"

        st.error(f"**🔍 最も可能性が高い原因：{main_cause}**\n\nそのため、{detail}")
        
        suggested_min_freq = max(1, min_freq - 1)
        
        st.markdown(f"""
        <div style="margin-top: 16px; margin-bottom: 8px; font-weight: bold; color: #1976d2;">💡 推奨されるアクション</div>
        <div style="background-color: #f0f7ff; border: 2px solid #90caf9; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
            <span style="font-size: 1.05em; font-weight: bold; color: #1565c0;">1. 最低出現回数を下げる</span><br>
            <span style="color: #333; font-size: 0.95em;">左サイドバーの設定を <b>{min_freq} → {suggested_min_freq}</b> に変更して再実行してください。</span>
        </div>
        <div style="margin-left: 8px; color: #333; font-size: 0.95em; line-height: 1.8;">
            <div style="margin-bottom: 8px;"><b>2. より投稿数が多く、具体的な本文を含むCSVに差し替える</b></div>
            <div><b>3. 必要に応じて「ノイズ・スパム判定語を表示する」をONにして除外内容を確認する</b></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        st.markdown("**▼ 正常に分析できるCSV例を試す**")
        st.download_button(
            label="📥 サンプルCSVで動作を確認する",
            data=SAMPLE_CSV,
            file_name="sample_sns_data.csv",
            mime="text/csv",
            help="フォーマットの確認や、お試し分析にご利用ください。"
        )
        
    with col_err_right:
        total_posts = len(df_raw)
        platforms = df_raw['platform'].value_counts()
        platform_str = " / ".join([f"{k} {v}件" for k, v in platforms.items()])
        
        extracted = metadata.get('extracted_words_count', 0)
        passed = metadata.get('passed_words_count', 0)
        spam_dropped = metadata.get('spam_dropped_count', 0)
        valid_posts = metadata.get('valid_posts_count', 0)
        
        st.markdown(f"""
        <div style="background-color: #f9f9fc; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0;">
            <strong style="color: #333; font-size: 1.1em;">📊 今回の解析結果</strong><br><br>
            <span style="color: #555;">読み込み投稿数：</span> <b style="font-size: 1.1em;">{total_posts}件</b><br>
            <span style="color: #777; font-size: 0.85em; margin-left: 12px;">媒体内訳：{platform_str}</span><br>
            <span style="color: #777; font-size: 0.85em; margin-left: 12px;">スパム除外：{spam_dropped}件</span><br>
            <span style="color: #777; font-size: 0.85em; margin-left: 12px;">有効投稿数：<b style="color: #333;">{valid_posts}件</b></span><br><br>
            <span style="color: #555;">抽出された候補語数：</span> <b style="font-size: 1.1em;">{extracted}件</b><br>
            <span style="color: #555;">しきい値を通過した語数：</span> <b style="color: #d32f2f; font-size: 1.2em;">{passed}件</b><br><br>
            <hr style="margin: 12px 0; border: none; border-top: 1px dashed #ccc;">
            <strong style="color: #555; font-size: 0.95em;">⚙️ 現在の設定値</strong><br>
            <span style="color: #333; font-size: 0.95em;">最低出現回数： <b style="font-size: 1.1em; color: #1976d2;">{min_freq}</b></span><br>
            <span style="color: #666; font-size: 0.9em;">ノイズ判定語表示： <b>{'ON' if show_noise else 'OFF'}</b></span>
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ==========================================
# 6. 結果の事後処理 (ランキング・サマリーの構築)
# ==========================================
df_display = df if 'is_noise' not in df.columns or show_noise else df[~df['is_noise']].copy()
df_display['duration_hours'] = df_display.get('duration_hours', 1.0)

# 💡 広がり(Network)は絶対条件から外し、「広がり」か「新規性(Novelty)」のどちらかがあればS昇格を許容
has_network = (df_display['conversion_z'] > 0) | (df_display['bridge_z'] > 0)
is_emerging = (df_display['novelty_z'] >= 0.5) 
is_spike = df_display['duration_hours'] < 1.0  # 1時間未満の局所集中はスパイクとして弾く
is_high_score = (df_display['score_eos'] >= 50) | (df_display['score_css'] >= 50)

# 💡 Sランクの条件緩和（パターン1救済）
s_condition = (~is_spike) & is_high_score & (has_network | is_emerging)

s_candidates = df_display[s_condition].sort_values(by=['score_eos', 'score_css'], ascending=[False, False])

top3_indices = s_candidates.head(3).index
df_display['Rank_Num'] = ""

if len(top3_indices) > 0: df_display.loc[top3_indices[0], 'Rank_Num'] = "①"
if len(top3_indices) > 1: df_display.loc[top3_indices[1], 'Rank_Num'] = "②"
if len(top3_indices) > 2: df_display.loc[top3_indices[2], 'Rank_Num'] = "③"

# A/Sの境界判定
def set_priority(row):
    if row['Rank_Num'] != "": 
        return "🔥 S (最優先)"
    if row['score_css'] >= 45 or row['score_eos'] >= 45 or row['engagement_z'] >= 0.7 or row['freq_z'] >= 0.7: 
        return "👀 A (保留)"
    return "➖ C (見送り)"

df_display['priority'] = df_display.apply(set_priority, axis=1)

df_display['text_content_type'] = df_display.apply(
    lambda r: "保留" if r['priority'] == "👀 A (保留)" else r['text_content_type'], 
    axis=1
)

# 💡 AとCの理由の明文化と解像度アップ
def enrich_card_data(row):
    original_ctype = row['text_content_type']
    pri = row['priority']
    rank = row['Rank_Num']
    duration = row.get('duration_hours', 0)
    has_net = (row.get('conversion_z', 0) > 0) or (row.get('bridge_z', 0) > 0)
    
    if pri == "🔥 S (最優先)":
        if rank == "①": reason = "圧倒的な成長率と新規性を持ち、今すぐ先回りすべき本命"
        elif rank == "②": reason = "関連テーマへの広がりが強く、独自の切り口で狙える"
        else: reason = "反応が急増しており、継続監視しつつ先読みが効く"
            
        if original_ctype == "先読み型": action = "今すぐ仕込み投稿"
        elif original_ctype == "解説型": action = "今すぐ解説投稿"
        elif original_ctype == "比較型": action = "今すぐ比較投稿"
        elif original_ctype == "まとめ型": action = "今すぐまとめ投稿"
        else: action = "今すぐ投稿"
        return action, reason
        
    elif pri == "👀 A (保留)":
        if duration < 1.0:
            return "様子見", "短期間の局地的な反応（スパイク）のため、継続するか様子見"
        elif not has_net:
            return "監視継続", "反応や新規性はあるが、関連テーマへの広がりが弱く今すぐ仕込むには根拠不足"
        else:
            return "監視継続", "注目候補ではあるが、観測期間や投稿数が少なく継続判定に届いていないため様子見"
            
    else: 
        if duration < 1.0:
            return "今回は見送り", "反応が弱く、継続性もない単発の投稿のため見送り"
        elif row['score_css'] >= 30:
            return "今回は見送り", "話題は残っているが、伸びが止まっている"
        else:
            return "今回は見送り", "話題力・ポテンシャル共に低迷しており優先度が低い"

df_display[['action', 'reason']] = df_display.apply(lambda r: pd.Series(enrich_card_data(r)), axis=1)

priority_order = ["🔥 S (最優先)", "👀 A (保留)", "➖ C (見送り)"]
df_display['priority'] = pd.Categorical(df_display['priority'], categories=priority_order, ordered=True)
df_display = df_display.sort_values(by=['priority', 'action', 'score_eos', 'score_css'], ascending=[True, True, False, False])

df_display['plot_label'] = df_display.apply(lambda r: r['Rank_Num'] if r['Rank_Num'] else "", axis=1)

# 💡 スコアのフォーマット処理 (一覧表での検証用)
for col in ['novelty_z', 'growth_z', 'sustainability_z', 'conversion_z', 'bridge_z']:
    if col in df_display.columns:
        df_display[col] = df_display[col].round(2)

# ==========================================
# 7. UI 描画 (結果画面)
# ==========================================
st.markdown("<div style='color: #aaa; font-size: 0.85em; margin-bottom: 8px;'>分析完了：注目テーマと投稿企画案を確認できます。</div>", unsafe_allow_html=True)

st.subheader("💡 今回の判定結果")

count_s = len(df_display[df_display['priority'] == "🔥 S (最優先)"])
count_a = len(df_display[df_display['priority'] == "👀 A (保留)"])
count_c = len(df_display[df_display['priority'] == "➖ C (見送り)"])

st.markdown(f"""
<div style="display: flex; gap: 16px; margin-bottom: 16px;">
    <div style="background: #f0f7ff; border: 1px solid #90caf9; border-radius: 8px; padding: 12px 24px; text-align: center; flex: 1;">
        <div style="font-size: 0.9em; color: #1565c0; font-weight: bold;">S (最優先)</div>
        <div style="font-size: 1.5em; font-weight: bold; color: #0d47a1; margin: 4px 0;">{count_s}件</div>
        <div style="font-size: 0.8em; color: #1565c0;">今すぐ着手</div>
    </div>
    <div style="background: #f3e5f5; border: 1px solid #ce93d8; border-radius: 8px; padding: 12px 24px; text-align: center; flex: 1;">
        <div style="font-size: 0.9em; color: #6a1b9a; font-weight: bold;">A (保留)</div>
        <div style="font-size: 1.5em; font-weight: bold; color: #4a148c; margin: 4px 0;">{count_a}件</div>
        <div style="font-size: 0.8em; color: #6a1b9a;">監視継続</div>
    </div>
    <div style="background: #f5f5f5; border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px 24px; text-align: center; flex: 1;">
        <div style="font-size: 0.9em; color: #616161; font-weight: bold;">C (見送り)</div>
        <div style="font-size: 1.5em; font-weight: bold; color: #424242; margin: 4px 0;">{count_c}件</div>
        <div style="font-size: 0.8em; color: #616161;">今回は見送り</div>
    </div>
</div>
""", unsafe_allow_html=True)

if count_s == 0:
    if count_a > 0:
        a_reasons = df_display[df_display['priority'] == "👀 A (保留)"]['reason'].tolist()
        if any("スパイク" in r for r in a_reasons):
            msg = "短期間の局地的な反応（スパイク）は確認されましたが、継続するか不透明なため、今回は「保留」と判定しました。"
        elif any("広がりが弱く" in r for r in a_reasons):
            msg = "一部の語に反応はありますが、関連テーマへの広がりが弱く、今すぐ仕込むには根拠不足のため「保留」と判定しました。"
        else:
            msg = "注目候補は抽出されましたが、最優先で着手すべき基準には届かず、「保留」判定となりました。"
    else:
        msg = "一部の語に反応は観測されましたが、継続性と広がりが弱く、今回は「見送り」判定となりました。"
        
    st.info(f"💡 **現在、今すぐ着手すべき強い推奨案（Sランク）はありません。**\n\n{msg}\n\n※ 詳細な根拠は下部の一覧表でご確認ください。")
else:
    top3_ideas = df_display[df_display['Rank_Num'] != ""].sort_values(by='Rank_Num')
    for _, row in top3_ideas.iterrows():
        st.markdown(f"""
        <div style="margin-bottom: 32px; padding-bottom: 4px;">
            <div style="display: flex; align-items: center; margin-bottom: 6px;">
                <span style="font-size: 1.4em; color: #d32f2f; font-weight: bold; margin-right: 12px;">{row['Rank_Num']}</span>
                <span style="font-size: 1.2em; font-weight: bold; margin-right: 16px;">{row['token']}</span>
                <span style="background-color: #f0f4f8; border: 1px solid #d0e2f3; color: #1976d2; padding: 2px 10px; border-radius: 12px; font-size: 0.85em; font-weight: bold; margin-right: 8px;">{row['action']}</span>
                <span style="color: #666; font-size: 0.85em;">（{row['text_content_type']}）</span>
            </div>
            <div style="color: #666; font-size: 0.9em; margin-left: 40px; line-height: 1.5;">{row['reason']}</div>
        </div>
        """, unsafe_allow_html=True)

# --- B. トレンドマップ ---
st.subheader("📊 トレンド四象限マップ")
st.markdown("<div style='color: #333; font-weight: bold; font-size: 0.95em; margin-top: 8px; margin-bottom: 16px;'>🗺️ マップの見方： [左上] 先回り候補 ／ [右上] 本命 ／ [右下] 後追い ／ [左下] 見送り</div>", unsafe_allow_html=True)

color_discrete_map = {
    "先読み型": "#1976D2", 
    "解説型": "#0288D1",   
    "比較型": "#0097A7",   
    "まとめ型": "#388E3C", 
    "保留": "#9FA8DA",     
    "見送り": "#BDBDBD"    
}
category_orders = {"text_content_type": ["先読み型", "解説型", "比較型", "まとめ型", "保留", "見送り"]}

fig = px.scatter(
    df_display, x="score_css", y="score_eos", text="plot_label", size="freq_raw", color="text_content_type",
    hover_name="token", hover_data={"plot_label": False, "text_content_type": True, "action": True, "freq_raw": True},
    labels={"score_css": "話題力 (Current Strength)", "score_eos": "ポテンシャル (Emerging Opportunity)", "text_content_type": "推奨投稿型", "token": "キーワード"},
    color_discrete_map=color_discrete_map,
    category_orders=category_orders,
    height=550
)
fig.update_traces(textposition='top right', textfont_size=18, textfont_color="#d32f2f")
fig.add_hline(y=50, line_dash="dot", line_color="gray")
fig.add_vline(x=50, line_dash="dot", line_color="gray")
fig.update_layout(xaxis_range=[0, 105], yaxis_range=[0, 105], margin=dict(t=10, b=10, l=10, r=10))
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- C. アクション一覧表 ---
st.subheader("📋 行動計画・キーワード一覧")
st.caption("S=今すぐ着手 / A=監視しつつ検討 / C=今回は見送り")

# 💡 一覧表に「ブラックボックスを解明する」内部スコアを追加
view_cols = {
    'priority': '優先度',
    'token': 'キーワード', 
    'action': '推奨アクション',
    'text_content_type': '推奨投稿型',
    'reason': '判定理由',
    'score_css': '話題力(CSS)', 
    'score_eos': 'ポテンシャル(EOS)',
    'novelty_z': '新規性',
    'growth_z': '成長率',
    'sustainability_z': '継続性',
    'conversion_z': '広がり'
}

st.dataframe(
    df_display[list(view_cols.keys())].rename(columns=view_cols),
    use_container_width=True, hide_index=True
)

with st.expander("💡 投稿型の意味と使い分け", expanded=False):
    st.markdown("""
    * **先読み型:** まだ競争が浅く、これから伸びるテーマ。いち早く発信することで第一人者ポジションを狙えます。
    * **解説型:** 今話題になり始めているテーマ。検索需要に応える図解や基本解説が刺さります。
    * **比較型:** 関連語との結びつきが強いテーマ。「AとBの違い」「どっちを選ぶべきか」のコンテンツが有効です。
    * **まとめ型:** すでに巨大なバズになっているテーマ。事例やみんなの反応をまとめた保存用のコンテンツが適しています。
    """)
