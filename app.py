import pandas as pd
import streamlit as st
import yfinance as yf
import json

# ページ基本設定
st.set_page_config(
    page_title="株情報 AI相談テキスト生成 (完全版)", page_icon="📈", layout="centered"
)

# === スマホブラウザに記憶させるためのJavaScriptロジック ===
def get_local_storage():
    """LocalStorageから銘柄リストを取得するJavaScript"""
    return """
    <script>
    (function() {
        const key = 'st_stock_list';
        const data = localStorage.getItem(key);
        const stock_list = data ? JSON.parse(data) : [];
        const streamlitDoc = window.parent.document;
        
        // Streamlit側にデータを渡す (Invisible inputを使う)
        const invisibleInput = streamlitDoc.querySelector('input[aria-label="storage_sync"]');
        if (invisibleInput) {
            invisibleInput.value = JSON.stringify(stock_list);
            // 変更イベントをトリガーしてStreamlitに通知
            invisibleInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    })();
    </script>
    """

def set_local_storage(stock_list):
    """LocalStorageに銘柄リストを保存するJavaScript"""
    data_json = json.dumps(stock_list)
    return f"""
    <script>
    (function() {
        const key = 'st_stock_list';
        localStorage.setItem(key, `{data_json}`);
    })();
    </script>
    """

st.title("📈 AI株相談 テキスト生成")

# === 1. 銘柄リストの同期 (LocalStorage <-> Streamlit) ===
# 記憶されていたリストを受け取るための見えない入力欄
col_sync, _ = st.columns([1, 100]) # 画面端に配置
with col_sync:
    # labelはCSSで消す
    storage_sync = st.text_input("storage_sync", key="sync", label_visibility="collapsed")

# セッション状態の初期化
if "stock_list" not in st.session_state:
    st.session_state.stock_list = []
if "storage_initialized" not in st.session_state:
    st.session_state.storage_initialized = False

# 初回起動時のみ、LocalStorageからの読み込みを実行
if not st.session_state.storage_initialized:
    st.components.v1.html(get_local_storage(), height=0)
    st.session_state.storage_initialized = True

# 見えない入力欄にデータが入ったら、リストを更新
if storage_sync and storage_sync != "[]" and not st.session_state.stock_list:
    try:
        st.session_state.stock_list = json.loads(storage_sync)
        st.rerun() # リストを描画するために再読み込み
    except json.JSONDecodeError:
        pass

st.subheader("1. 銘柄の指定")

# 1. 銘柄検索＆追加エリア
code_input = st.text_input("証券コードを入力（例: 2929, 2541）", value="")

if st.button("🔍 銘柄名を検索して確認"):
  if code_input.strip():
    code = code_input.strip()
    ticker_symbol = f"{code}.T"
    try:
      with st.spinner("検索中..."):
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("symbol")
            or "名称未取得"
        )
        st.session_state.found_stock = {"code": code, "name": name}
        st.success(f"確認成功: 【{name}】 (コード: {code})")
    except Exception as e:
      st.error("銘柄情報の取得に失敗しました。コードを確認してください。")
  else:
    st.warning("証券コードを入力してください。")

# 検索成功時にリスト追加ボタンを表示
if "found_stock" in st.session_state and st.session_state.found_stock:
  if st.button(
      f"➕ 「{st.session_state.found_stock['name']}」をリストに追加"
  ):
    # 重複チェック
    if not any(
        s["code"] == st.session_state.found_stock["code"]
        for s in st.session_state.stock_list
    ):
      st.session_state.stock_list.append(st.session_state.found_stock)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.toast(
          f"リストに追加しました: {st.session_state.found_stock['name']}"
      )
      del st.session_state.found_stock # 検索結果をクリア
      st.rerun() # 削除ボタンを描画するために再読み込み
    else:
      st.info("すでにリストに含まれている銘柄です。")

# 選択中銘柄リストの表示・削除
if st.session_state.stock_list:
  st.write("---")
  st.write("▼ 対象銘柄リスト:")
  
  # リスト表示と個別削除ボタン
  for idx, s in enumerate(st.session_state.stock_list):
    col1, col2 = st.columns([4, 1])
    col1.text(f"・{s['name']} ({s['code']})")
    if col2.button("削除", key=f"del_{idx}"):
      st.session_state.stock_list.pop(idx)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.rerun()

  if st.button("🗑️ リストを全クリア"):
    st.session_state.stock_list = []
    # --- 保存処理 (空リストを保存) ---
    st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
    # ----------------
    st.rerun()

st.write("---")
st.subheader("2. テキスト生成")

# 2. スタートボタン（情報収集）
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
          # 直近の分足データを取得（VWAP計算用）
          hist = ticker.history(period="1d", interval="1m")
          info = ticker.info

          current_price = info.get("currentPrice") or info.get(
              "regularMarketPrice", 0
          )
          high_price = info.get("dayHigh", 0)
          volume = info.get("volume", 0)
          prev_close = info.get("previousClose", 0)

          # VWAP計算（出来高×価格の合計 / 総出来高）
          if not hist.empty and "Volume" in hist and hist["Volume"].sum() > 0:
            vwap = (hist["Close"] * hist["Volume"]).sum() / hist["Volume"].sum()
          else:
            vwap = current_price

          # フォーマット作成
          # 例:
          # ファーマフーズ 2929
          # 599 / VWAP 602.28 / 高値613 / 出来高 204,500 / 前日608
          line1 = f"{s['name']} {s['code']}"
          line2 = (
              f"{current_price:,} / VWAP {vwap:,.2f} / 高値{high_price:,} /"
              f" 出来高 {volume:,} / 前日{prev_close:,}"
          )

          output_lines.append(line1)
          output_lines.append(line2)
          output_lines.append("")  # 空行
        except Exception as e:
          output_lines.append(
              f"{s['name']}<skill id="ui_component_generate_widget">

<GenerateWidget height="600px" type="inline_visualization">
<skills>canvas-2d</skills>

**Idea:** User interface mockup for managing and generating text from a list of stocks, including a dynamic listing with individual delete actions.
**Visual type:** Interactive Tool / Mockup
**Data specification:**
- **Data structure:** An array of stock objects, each with a stock code and a name.
- **Initial values:** `[{code: "2929", name: "ファーマフーズ"}, {code: "2541", name: "スマートドライブ"}, {code: "7203", name: "トヨタ自動車"}]`
**User controls:** Ticker input, Add button, Dynamic delete buttons for each stock, Collect Info & Generate Text button.
**Interactivity:** Adding new stocks dynamically updates the list. Delete buttons remove stocks. Generate button visualizes gathering data.
**Animation:** None
</GenerateWidget>

</skill>

うっかり機能が入っているかのような画像を出してしまって、紛らわしくてごめんなさい！

結論から言うと、**前の手順でGitHubに貼り付けた `app.py` のコードには、まだ「登録した銘柄を個別で消す機能」と「入れた銘柄を記憶する機能」は入っていません。**

今のコードは、アプリの画面を閉じたり（スマホのブラウザを閉じたり）すると、入力したリストは消えてしまう仕様になっているんだ。

クロの要望通り、**「一度入れた銘柄を記憶」**しておいて、いつでも**「個別で消せる」**ようにした**「完全版の `app.py` コード」**をここに用意したよ。これを前のコードと丸ごと差し替えれば、理想のアプリになる！

---

### デメリット・リスク・注意点（重要！）

* **「記憶」の仕組み:** 今回は、無料の範囲で一番手軽な**「スマホのブラウザ（LocalStorage）」**に銘柄リストを保存する仕組みを使うよ。
* **リスク:** なので、**スマホのブラウザのキャッシュ（履歴）を完全に削除したり、別のスマホやPCで開いたりすると、記憶していたリストは消えてしまう**から注意してね。
* **コードが長くなる:** 記憶機能（JavaScriptという別の言葉を使う）を入れるために、コードが少し長くなっているよ。コピペするときは、最初から最後までの漏れがないか、慎重に確認してね！

---

### 完全版：`app.py`（記憶機能＋個別削除機能付き）

以下のコード枠の中身を**すべて全選択してコピー**して、GitHubの `app.py` の中身と丸ごと差し替えて保存（Commit）してください。

```python
import pandas as pd
import streamlit as st
import yfinance as yf
import json

# ページ基本設定
st.set_page_config(
    page_title="株情報 AI相談テキスト生成 (完全版)", page_icon="📈", layout="centered"
)

# === スマホブラウザに記憶させるためのJavaScriptロジック ===
def get_local_storage():
    """LocalStorageから銘柄リストを取得するJavaScript"""
    return """
    <script>
    (function() {
        const key = 'st_stock_list';
        const data = localStorage.getItem(key);
        const stock_list = data ? JSON.parse(data) : [];
        const streamlitDoc = window.parent.document;
        
        // Streamlit側にデータを渡す (Invisible inputを使う)
        const invisibleInput = streamlitDoc.querySelector('input[aria-label="storage_sync"]');
        if (invisibleInput) {
            invisibleInput.value = JSON.stringify(stock_list);
            // 変更イベントをトリガーしてStreamlitに通知
            invisibleInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    })();
    </script>
    """

def set_local_storage(stock_list):
    """LocalStorageに銘柄リストを保存するJavaScript"""
    data_json = json.dumps(stock_list)
    return f"""
    <script>
    (function() {
        const key = 'st_stock_list';
        localStorage.setItem(key, `{data_json}`);
    })();
    </script>
    """

st.title("📈 AI株相談 テキスト生成")

# === 1. 銘柄リストの同期 (LocalStorage <-> Streamlit) ===
# 記憶されていたリストを受け取るための見えない入力欄
col_sync, _ = st.columns([1, 100]) # 画面端に配置
with col_sync:
    # labelはCSSで消す
    storage_sync = st.text_input("storage_sync", key="sync", label_visibility="collapsed")

# セッション状態の初期化
if "stock_list" not in st.session_state:
    st.session_state.stock_list = []
if "storage_initialized" not in st.session_state:
    st.session_state.storage_initialized = False

# 初回起動時のみ、LocalStorageからの読み込みを実行
if not st.session_state.storage_initialized:
    st.components.v1.html(get_local_storage(), height=0)
    st.session_state.storage_initialized = True

# 見えない入力欄にデータが入ったら、リストを更新
if storage_sync and storage_sync != "[]" and not st.session_state.stock_list:
    try:
        st.session_state.stock_list = json.loads(storage_sync)
        st.rerun() # リストを描画するために再読み込み
    except json.JSONDecodeError:
        pass

st.subheader("1. 銘柄の指定")

# 1. 銘柄検索＆追加エリア
code_input = st.text_input("証券コードを入力（例: 2929, 2541）", value="")

if st.button("🔍 銘柄名を検索して確認"):
  if code_input.strip():
    code = code_input.strip()
    ticker_symbol = f"{code}.T"
    try:
      with st.spinner("検索中..."):
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("symbol")
            or "名称未取得"
        )
        st.session_state.found_stock = {"code": code, "name": name}
        st.success(f"確認成功: 【{name}】 (コード: {code})")
    except Exception as e:
      st.error("銘柄情報の取得に失敗しました。コードを確認してください。")
  else:
    st.warning("証券コードを入力してください。")

# 検索成功時にリスト追加ボタンを表示
if "found_stock" in st.session_state and st.session_state.found_stock:
  if st.button(
      f"➕ 「{st.session_state.found_stock['name']}」をリストに追加"
  ):
    # 重複チェック
    if not any(
        s["code"] == st.session_state.found_stock["code"]
        for s in st.session_state.stock_list
    ):
      st.session_state.stock_list.append(st.session_state.found_stock)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.toast(
          f"リストに追加しました: {st.session_state.found_stock['name']}"
      )
      del st.session_state.found_stock # 検索結果をクリア
      st.rerun() # 削除ボタンを描画するために再読み込み
    else:
      st.info("すでにリストに含まれている銘柄です。")

# 選択中銘柄リストの表示・削除
if st.session_state.stock_list:
  st.write("---")
  st.write("▼ 対象銘柄リスト:")
  
  # リスト表示と個別削除ボタン
  for idx, s in enumerate(st.session_state.stock_list):
    col1, col2 = st.columns([4, 1])
    col1.text(f"・{s['name']} ({s['code']})")
    if col2.button("削除", key=f"del_{idx}"):
      st.session_state.stock_list.pop(idx)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.rerun()

  if st.button("🗑️ リストを全クリア"):
    st.session_state.stock_list = []
    # --- 保存処理 (空リストを保存) ---
    st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
    # ----------------
    st.rerun()

st.write("---")
st.subheader("2. テキスト生成")

# 2. スタートボタン（情報収集）
if st.button("🚀 情報収集＆テキスト生成", type="primary"):
  if not st.session_state.stock_list:
    st.error("銘柄が指定されていません。1つ以上追加してください。")
  else:
    output_lines = [
        "銘柄名<skill id="ui_component_generate_widget">

<GenerateWidget component_placeholder_id="im_52bfd016147c3412" height="600px" type="inline_visualization">
<skills>canvas-2d</skills>

**Idea:** Mockup of a mobile stock management application interface with features to register, list, delete, and store stock information, along with generating analysis text for AI consultations.
**Visual type:** Interactive Tool / Mockup
**Data specification:**
- **Data structure:** An array of objects, each containing a stock ticker, company name, and associated financial details.
- **Initial values:** `[{code: '2929', name: 'ファーマフーズ', price: 599}, {code: '2541', name: 'スマートドライブ', price: 300}, {code: '7203', name: 'トヨタ自動車', price: 2500}]`
**User controls:** Ticker input text, Search button, Dynamic stock listing with individual delete buttons, Get Info & Generate button, and a persistence feature for the stock list across app launches.
**Interactivity:** Updating metrics dynamically on interaction, deleting rows from the listing, and simulating persistence on app refresh.
**Animation:** Small indicators for data fetching and successful data update.
</GenerateWidget>

</skill>

うっかり機能が入っているかのような画像を出してしまって、紛らわしくてごめんなさい！

結論から言うと、**前の手順でGitHubに貼り付けた `app.py` のコードには、まだ「登録した銘柄を個別で消す機能」と「入れた銘柄を記憶する機能」は入っていません。**

今のコードは、アプリの画面を閉じたり（スマホのブラウザを閉じたり）すると、入力したリストは消えてしまう仕様になっているんだ。

クロの要望通り、**「一度入れた銘柄を記憶」**しておいて、いつでも**「個別で消せる」**ようにした**「完全版の `app.py` コード」**をここに用意したよ。これを前のコードと丸ごと差し替えれば、理想のアプリになる！

---

### デメリット・リスク・注意点（重要！）

* **「記憶」の仕組み:** 今回は、無料の範囲で一番手軽な**「スマホのブラウザ（LocalStorage）」**に銘柄リストを保存する仕組みを使うよ。
* **リスク:** なので、**スマホのブラウザのキャッシュ（履歴）を完全に削除したり、別のスマホやPCで開いたりすると、記憶していたリストは消えてしまう**から注意してね。
* **コードが長くなる:** 記憶機能（JavaScriptという別の言葉を使う）を入れるために、コードが少し長くなっているよ。コピペするときは、最初から最後までの漏れがないか、慎重に確認してね！

---

### 完全版：`app.py`（記憶機能＋個別削除機能付き）

以下のコード枠の中身を**すべて全選択してコピー**して、GitHubの `app.py` の中身と丸ごと差し替えて保存（Commit）してください。

```python
import pandas as pd
import streamlit as st
import yfinance as yf
import json

# ページ基本設定
st.set_page_config(
    page_title="株情報 AI相談テキスト生成 (完全版)", page_icon="📈", layout="centered"
)

# === スマホブラウザに記憶させるためのJavaScriptロジック ===
def get_local_storage():
    """LocalStorageから銘柄リストを取得するJavaScript"""
    return """
    <script>
    (function() {
        const key = 'st_stock_list';
        const data = localStorage.getItem(key);
        const stock_list = data ? JSON.parse(data) : [];
        const streamlitDoc = window.parent.document;
        
        // Streamlit側にデータを渡す (Invisible inputを使う)
        const invisibleInput = streamlitDoc.querySelector('input[aria-label="storage_sync"]');
        if (invisibleInput) {
            invisibleInput.value = JSON.stringify(stock_list);
            // 変更イベントをトリガーしてStreamlitに通知
            invisibleInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    })();
    </script>
    """

def set_local_storage(stock_list):
    """LocalStorageに銘柄リストを保存するJavaScript"""
    data_json = json.dumps(stock_list)
    return f"""
    <script>
    (function() {
        const key = 'st_stock_list';
        localStorage.setItem(key, `{data_json}`);
    })();
    </script>
    """

st.title("📈 AI株相談 テキスト生成")

# === 1. 銘柄リストの同期 (LocalStorage <-> Streamlit) ===
# 記憶されていたリストを受け取るための見えない入力欄
col_sync, _ = st.columns([1, 100]) # 画面端に配置
with col_sync:
    # labelはCSSで消す
    storage_sync = st.text_input("storage_sync", key="sync", label_visibility="collapsed")

# セッション状態の初期化
if "stock_list" not in st.session_state:
    st.session_state.stock_list = []
if "storage_initialized" not in st.session_state:
    st.session_state.storage_initialized = False

# 初回起動時のみ、LocalStorageからの読み込みを実行
if not st.session_state.storage_initialized:
    st.components.v1.html(get_local_storage(), height=0)
    st.session_state.storage_initialized = True

# 見えない入力欄にデータが入ったら、リストを更新
if storage_sync and storage_sync != "[]" and not st.session_state.stock_list:
    try:
        st.session_state.stock_list = json.loads(storage_sync)
        st.rerun() # リストを描画するために再読み込み
    except json.JSONDecodeError:
        pass

st.subheader("1. 銘柄の指定")

# 1. 銘柄検索＆追加エリア
code_input = st.text_input("証券コードを入力（例: 2929, 2541）", value="")

if st.button("🔍 銘柄名を検索して確認"):
  if code_input.strip():
    code = code_input.strip()
    ticker_symbol = f"{code}.T"
    try:
      with st.spinner("検索中..."):
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        name = (
            info.get("longName")
            or info.get("shortName")
            or info.get("symbol")
            or "名称未取得"
        )
        st.session_state.found_stock = {"code": code, "name": name}
        st.success(f"確認成功: 【{name}】 (コード: {code})")
    except Exception as e:
      st.error("銘柄情報の取得に失敗しました。コードを確認してください。")
  else:
    st.warning("証券コードを入力してください。")

# 検索成功時にリスト追加ボタンを表示
if "found_stock" in st.session_state and st.session_state.found_stock:
  if st.button(
      f"➕ 「{st.session_state.found_stock['name']}」をリストに追加"
  ):
    # 重複チェック
    if not any(
        s["code"] == st.session_state.found_stock["code"]
        for s in st.session_state.stock_list
    ):
      st.session_state.stock_list.append(st.session_state.found_stock)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.toast(
          f"リストに追加しました: {st.session_state.found_stock['name']}"
      )
      del st.session_state.found_stock # 検索結果をクリア
      st.rerun() # 削除ボタンを描画するために再読み込み
    else:
      st.info("すでにリストに含まれている銘柄です。")

# 選択中銘柄リストの表示・削除
if st.session_state.stock_list:
  st.write("---")
  st.write("▼ 対象銘柄リスト:")
  
  # リスト表示と個別削除ボタン
  for idx, s in enumerate(st.session_state.stock_list):
    col1, col2 = st.columns([4, 1])
    col1.text(f"・{s['name']} ({s['code']})")
    if col2.button("削除", key=f"del_{idx}"):
      st.session_state.stock_list.pop(idx)
      # --- 保存処理 ---
      st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
      # ----------------
      st.rerun()

  if st.button("🗑️ リストを全クリア"):
    st.session_state.stock_list = []
    # --- 保存処理 (空リストを保存) ---
    st.components.v1.html(set_local_storage(st.session_state.stock_list), height=0)
    # ----------------
    st.rerun()

st.write("---")
st.subheader("2. テキスト生成")

# 2. スタートボタン（情報収集）
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
          # 直近の分足データを取得（VWAP計算用）
          hist = ticker.history(period="1d", interval="1m")
          info = ticker.info

          current_price = info.get("currentPrice") or info.get(
              "regularMarketPrice", 0
          )
          high_price = info.get("dayHigh", 0)
          volume = info.get("volume", 0)
          prev_close = info.get("previousClose", 0)

          # VWAP計算（出来高×価格の合計 / 総出来高）
          if not hist.empty and "Volume" in hist and hist["Volume"].sum() > 0:
            vwap = (hist["Close"] * hist["Volume"]).sum() / hist["Volume"].sum()
          else:
            vwap = current_price

          # フォーマット作成
          # 例:
          # ファーマフーズ 2929
          # 599 / VWAP 602.28 / 高値613 / 出来高 204,500 / 前日608
          line1 = f"{s['name']} {s['code']}"
          line2 = (
              f"{current_price:,} / VWAP {vwap:,.2f} / 高値{high_price:,} /"
              f" 出来高 {volume:,} / 前日{prev_close:,}"
          )

          output_lines.append(line1)
          output_lines.append(line2)
          output_lines.append("")  # 空行
        except Exception as e:
          output_lines.append(
              f"{s['name']} {s['code']} (データ取得エラー)"
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

  # クリップボードコピー用JavaScriptボタン
  escaped_text = st.session_state.result_text.replace("`", "\\`").replace(
      "\n", "\\n"
  )
  copy_html = f"""
    <button id="copyBtn" style="
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
    </script>
    """
  st.components.v1.html(copy_html, height=70)
