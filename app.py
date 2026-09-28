import streamlit as st
import yfinance as yf

st.title("📈 AI株相談 テキスト生成")

# セッション状態の初期化
if "stocks" not in st.session_state:
    st.session_state.stocks = []

# 1. 銘柄検索＆追加
col1, col2 = st.columns([3, 1])
with col1:
    code = st.text_input("証券コードを入力", placeholder="例: 2929")
with col2:
    search_btn = st.button("銘柄検索")

if search_btn and code:
    ticker_symbol = f"{code}.T"
    ticker = yf.Ticker(ticker_symbol)
    info = ticker.info
    name = info.get("longName") or info.get("shortName") or "不明な銘柄"
    
    st.session_state.stocks.append({"code": code, "name": name})
    st.success(f"追加: {name} ({code})")

# 選択中銘柄の表示
st.write("### 選択中の銘柄")
for s in st.session_state.stocks:
    st.text(f"・{s['name']} ({s['code']})")

# 2. スタートボタン（情報収集）
if st.button("🚀 情報収集スタート"):
    output_text = ""
    
    for s in st.session_state.stocks:
        ticker = yf.Ticker(f"{s['code']}.T")
        hist = ticker.history(period="2d", interval="1m") # 直近データ
        info = ticker.info
        
        current_price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        high_price = info.get("dayHigh", 0)
        volume = info.get("volume", 0)
        prev_close = info.get("previousClose", 0)
        
        # VWAP概算 (出来高×価格の総和 / 総出来高)
        if not hist.empty and "Volume" in hist and hist["Volume"].sum() > 0:
            vwap = (hist["Close"] * hist["Volume"]).sum() / hist["Volume"].sum()
        else:
            vwap = current_price
            
        output_text += f"{s['name']}　{s['code']}\n"
        output_text += f"{current_price:,} / VWAP {vwap:,.2f} / 高値{high_price:,} / 出来高 {volume:,} / 前日{prev_close:,}\n\n"
    
    st.session_state.result_text = output_text.strip()

# 3. テキスト出力とコピー
if "result_text" in st.session_state:
    st.text_area("出力結果", st.session_state.result_text, height=150)
    
    # クリップボードコピー用（JavaScript使用）
    st.components.v1.html(
        f"""
        <button onclick="navigator.clipboard.writeText(`{st.session_state.result_text}`)" 
                style="padding: 10px 20px; background-color: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">
            📋 クリップボードにコピー
        </button>
        """,
        height=50,
    )
