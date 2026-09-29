import json
import pandas as pd
import streamlit as st
import yfinance as yf

# ページ基本設定
st.set_page_config(
    page_title="株情報 AI相談テキスト生成", page_icon="📈", layout="centered"
)


# === スマホブラウザに記憶させるためのJavaScriptロジック ===
def get_local_storage():
  """LocalStorageから銘柄リストを取得するJavaScript"""
  return """<script>
(function() {
    const key = 'st_stock_list';
    const data = localStorage.getItem(key);
    const stock_list = data ? JSON.parse(data) : [];
    const streamlitDoc = window.parent.document;
    
    const invisibleInput = streamlitDoc.querySelector('input[aria-label="storage_sync"]');
    if (invisibleInput) {
        invisibleInput.value = JSON.stringify(stock_list);
        invisibleInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
})();
</script>"""


def set_local_storage(stock_list):
  """LocalStorageに銘柄リストを保存するJavaScript"""
  data_json = json.dumps(stock_list)
  return f"""<script>
(function() {{
    const key = 'st_stock_list';
    localStorage.setItem(key, `{data_json}`);
}})();
</script>"""


st.title("📈 AI株相談 テキスト生成")

# === 1. 銘柄リストの同期 (LocalStorage <-> Streamlit) ===
col_sync, _ = st.columns([1, 100])
with col_sync:
  storage_sync = st.text_input(
      "storage_sync", key="sync", label_visibility="collapsed"
  )

if "stock_list" not in st.session_state:
  st.session_state.stock_list = []
if "storage_initialized" not in st.session_state:
  st.session_state.storage_initialized = False

if not st.session_state.storage_initialized:
  st.components.v1.html(get_local_storage(), height=0)
  st.session_state.storage_initialized = True

if storage_sync and storage_sync != "[]" and not st.session_state.stock_list:
  try:
    st.session_state.stock_list = json.loads(storage_sync)
    st.rerun()
  except json.JSONDecodeError:
    pass

st.subheader("1. 銘柄の指定")

# 銘柄検索＆入力エリア
col_code, col_name = st.columns([1, 2])
with col_code:
  code_input = st.text_input("証券コード", value="", placeholder="例: 2929")
with col_name:
  custom_name_input = st.text_input(
      "銘柄名（自動検索可・手動変更可）",
      value="",
      placeholder="例: ファーマフーズ",
  )

if st.button("🔍 銘柄情報を自動検索してセット"):
  if code_input.strip():
    code = code_input.strip()
    ticker_symbol = f"{code}.T"
    try:
      with st.spinner("検索中..."):
        ticker = yf.Ticker(ticker_symbol)
        fetched_name = None

        # yfinanceから銘柄名の取得を試みる
        try:
          info = ticker.info
          fetched_name = (
              info.get("longName")
              or info.get("shortName")
              or info.get("symbol")
          )
        except Exception:
          pass

        if not fetched_name or fetched_name == f"{code}.T":
          fetched_name = f"銘柄_{code}"

        st.session_state.temp_code = code
        st.session_state.temp_name = fetched_name
        st.success(f"取得成功: 【{fetched_name}】 (コード: {code})")
    except Exception as e:
      st.error("銘柄情報の取得に失敗しました。")
  else:
    st.warning("証券コードを入力してください。")

# 追加ボタン（手動入力された名称があればそれを優先）
add_code = code_input.strip()
add_name = (
    custom_name_input.strip()
    or getattr(st.session_state, "temp_name", "")
    or f"銘柄_{add_code}"
)

if add_code and st.button(f"➕ 「{add_name} ({add_code})」をリストに追加"):
  if not any(s["code"] == add_code for s in st.session_state.stock_list):
    st.session_state.stock_list.append({"code": add_code, "name": add_name})
    st.components.v1.html(
        set_local_storage(st.session_state.stock_list), height=0
    )
    st.toast(f"リストに追加しました: {add_name}")
    if "temp_name" in st.session_state:
      del st.session_state.temp_name
    st.rerun()
  else:
    st.info("すでにリストに含まれている銘柄です。")

# 選択中銘柄リストの表示・削除
if st.session_state.stock_list:
  st.write("---")
  st.write("▼ 対象銘柄リスト:")

  for idx, s in enumerate(st.session_state.stock_list):
    col1, col2 = st.columns([4, 1])
    col1.text(f"・{s['name']} ({s['code']})")
    if col2.button("削除", key=f"del_{idx}"):
      st.session_state.stock_list.pop(idx)
      st.components.v1.html(
          set_local_storage(st.session_state.stock_list), height=0
      )
      st.rerun()

  if st.button("🗑️ リストを全クリア"):
    st.session_state.stock_list = []
    st.components.v1.html(
        set_local_storage(st.session_state.stock_list), height=0
    )
    st.rerun()

st.write("---")
st.subheader("2. テキスト生成")

# スタートボタン（情報収集）
if st.button("🚀 情報収集＆テキスト生成", type="primary"):
  if not st.session_state.stock_list:
    st.error("銘柄が指定されていません。1つ以上追加してください。")
  else:
    output_lines = [
        "銘柄名 証券コード",
        "現在株価 / VWAP / 高値 / 出来高 / 前日値 /",
        "",
    ]

    with st.spinner("最新データを取得中..."):
      for s in st.session_state.stock_list:
        try:
          ticker = yf.Ticker(f"{s['code']}.T")

          # 直近の当日の1分足データと日足データを精度高く取得
          hist_1d = ticker.history(period="1d", interval="1m")
          hist_5d = ticker.history(period="5d", interval="1d")

          # 1. 現在株価・出来高の最新値
          fast_info = getattr(ticker, "fast_info", {})
          current_price = fast_info.get("lastPrice") or (
              hist_1d["Close"].iloc[-1] if not hist_1d.empty else 0
          )
          prev_close = fast_info.get("previousClose") or (
              hist_5d["Close"].iloc[-2] if len(hist_5d) >= 2 else current_price
          )

          # 当日の高値・出来高
          if not hist_1d.empty:
            high_price = hist_1d["High"].max()
            volume = hist_1d["Volume"].sum()
            # VWAP（出来高加重平均価格）の正確な計算
            vwap = (hist_1d["Close"] * hist_1d["Volume"]).sum() / volume if volume > 0 else current_price
          elif not hist_5d.empty:
            high_price = hist_5d["High"].iloc[-1]
            volume = hist_5d["Volume"].iloc[-1]
            vwap = current_price
          else:
            high_price = current_price
            volume = 0
            vwap = current_price

          line1 = f"{s['name']} {s['code']}"
          line2 = (
              f"{current_price:,.1f} / VWAP {vwap:,.2f} / 高値{high_price:,.1f}"
              f" / 出来高 {int(volume):,} / 前日{prev_close:,.1f}"
          )

          output_lines.append(line1)
          output_lines.append(line2)
          output_lines.append("")

        except Exception as e:
          output_lines.append(
              f"{s['name']} {s['code']} (データ取得エラー: {e})"
          )
          output_lines.append("")

    st.session_state.result_text = "\n".join(output_lines).strip()

# 3. テキスト出力とコピー機能
if "result_text" in st.session_state and st.session_state.result_text:
  st.subheader("3. 出力結果")
  st.text_area(
      "生成されたテキスト",
      st.session_state.result_text,
      height=200,
  )

  escaped_text = st.session_state.result_text.replace("`", "\\`").replace(
      "\n", "\\n"
  )
  copy_html = f"""<button id="copyBtn" style="
    width: 100%;
    padding: 12px;
    background-color: #FF4B4B;
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: bold;
    font-size: 16px;
    cursor: pointer;
">📋 クリップボードにコピー</button>

<script>
document.getElementById('copyBtn').addEventListener('click', function() {{
    navigator.clipboard.writeText(`{escaped_text}`).then(function() {{
        alert('クリップボードにコピーしました！');
    }}).catch(function(err) {{
        alert('コピーに失敗しました: ' + err);
    }});
}});
</script>"""
  st.components.v1.html(copy_html, height=70)
