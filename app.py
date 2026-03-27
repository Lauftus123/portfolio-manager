import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from openai import OpenAI
import json
import os

# --- Page Config ---
st.set_page_config(
    page_title="InvestIQ - AI Portfolio Manager",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #334155;
    }
    .positive { color: #22c55e; }
    .negative { color: #ef4444; }
    [data-testid="stSidebar"] { background-color: #0f172a; }
</style>
""", unsafe_allow_html=True)

# --- Init Session State ---
if "holdings" not in st.session_state:
    st.session_state.holdings = [
        {"symbol": "AAPL", "name": "Apple Inc.", "type": "Stock", "qty": 25, "avg_cost": 142.5, "price": 178.72, "sector": "Technology"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "type": "Stock", "qty": 15, "avg_cost": 285.0, "price": 415.5, "sector": "Technology"},
        {"symbol": "BTC",  "name": "Bitcoin",         "type": "Crypto","qty": 0.5,"avg_cost": 42000,"price": 67500, "sector": "Crypto"},
        {"symbol": "VTI",  "name": "Vanguard Total Market ETF","type":"ETF","qty":30,"avg_cost":210.0,"price":265.4,"sector":"Broad Market"},
        {"symbol": "AGG",  "name": "US Aggregate Bond ETF","type":"Bond","qty":50,"avg_cost":100.5,"price":98.2,"sector":"Fixed Income"},
        {"symbol": "AMZN", "name": "Amazon.com Inc.", "type": "Stock", "qty": 20, "avg_cost": 130.0, "price": 185.6, "sector": "Consumer"},
        {"symbol": "GLD",  "name": "SPDR Gold Shares","type": "Commodity","qty":15,"avg_cost":180.0,"price":215.3,"sector":"Commodities"},
    ]

if "transactions" not in st.session_state:
    st.session_state.transactions = [
        {"date": "2025-06-15", "symbol": "AAPL", "type": "BUY",  "qty": 25,  "price": 142.5,  "total": 3562.5},
        {"date": "2025-08-20", "symbol": "MSFT", "type": "BUY",  "qty": 15,  "price": 285.0,  "total": 4275.0},
        {"date": "2025-10-01", "symbol": "BTC",  "type": "BUY",  "qty": 0.5, "price": 42000,  "total": 21000},
        {"date": "2025-07-10", "symbol": "VTI",  "type": "BUY",  "qty": 30,  "price": 210.0,  "total": 6300.0},
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar ---
with st.sidebar:
    st.markdown("## 📈 InvestIQ")
    st.markdown("*AI Portfolio Manager*")
    st.divider()
    page = st.radio(
        "Navigation",
        ["Dashboard", "Portfolio", "Transactions", "AI Advisor"],
        label_visibility="collapsed"
    )
    st.divider()
    st.caption("⚠️ Not financial advice.")

# ============================================================
# HELPER
# ============================================================
def get_df():
    df = pd.DataFrame(st.session_state.holdings)
    df["value"]   = df["qty"] * df["price"]
    df["cost"]    = df["qty"] * df["avg_cost"]
    df["pnl"]     = df["value"] - df["cost"]
    df["pnl_pct"] = ((df["pnl"] / df["cost"]) * 100).round(2)
    return df

# ============================================================
# DASHBOARD
# ============================================================
if page == "Dashboard":
    st.title("📊 Dashboard")
    df = get_df()

    total_value = df["value"].sum()
    total_cost  = df["cost"].sum()
    total_pnl   = total_value - total_cost
    pnl_pct     = (total_pnl / total_cost * 100) if total_cost > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Value",    f"${total_value:,.2f}")
    c2.metric("Total P&L",      f"${total_pnl:,.2f}",   f"{pnl_pct:+.2f}%")
    c3.metric("Holdings",       len(df))
    c4.metric("Total Invested", f"${total_cost:,.2f}")

    st.divider()
    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("Asset Allocation")
        alloc = df.groupby("type")["value"].sum().reset_index()
        fig = px.pie(alloc, values="value", names="type", hole=0.5,
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_layout(margin=dict(t=0, b=0, l=0, r=0), showlegend=True,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Holdings")
        display = df[["symbol", "name", "qty", "price", "value", "pnl_pct"]].copy()
        display.columns = ["Symbol", "Name", "Qty", "Price", "Value", "P&L %"]
        st.dataframe(display.style.format({
            "Price": "${:.2f}", "Value": "${:,.2f}", "P&L %": "{:+.2f}%"
        }).applymap(
            lambda v: "color: #22c55e" if isinstance(v, float) and v > 0
            else ("color: #ef4444" if isinstance(v, float) and v < 0 else ""),
            subset=["P&L %"]
        ), use_container_width=True, hide_index=True)

# ============================================================
# PORTFOLIO
# ============================================================
elif page == "Portfolio":
    st.title("💼 Portfolio")

    with st.expander("➕ Add New Holding", expanded=False):
        with st.form("add_holding"):
            cc1, cc2 = st.columns(2)
            symbol   = cc1.text_input("Symbol (e.g. AAPL)").upper()
            name     = cc2.text_input("Name")
            cc3, cc4, cc5, cc6 = st.columns(4)
            asset_type = cc3.selectbox("Type", ["Stock","ETF","Bond","Crypto","Commodity","Other"])
            qty      = cc4.number_input("Quantity",    min_value=0.0, step=0.01)
            avg_cost = cc5.number_input("Avg Cost",    min_value=0.0, step=0.01)
            price    = cc6.number_input("Current Price",min_value=0.0,step=0.01)
            sector   = st.text_input("Sector (optional)")
            if st.form_submit_button("Add Holding") and symbol and name:
                st.session_state.holdings.append({
                    "symbol": symbol, "name": name, "type": asset_type,
                    "qty": qty, "avg_cost": avg_cost, "price": price, "sector": sector
                })
                st.success(f"Added {symbol}!")
                st.rerun()

    df = get_df()
    st.subheader("All Holdings")

    for i, row in df.iterrows():
        col1, col2, col3, col4, col5, col6 = st.columns([2, 1, 1, 1, 1, 0.5])
        col1.markdown(f"**{row['symbol']}** — {row['name']}")
        col2.markdown(f"Qty: **{row['qty']}**")
        col3.markdown(f"${row['price']:,.2f}")
        col4.markdown(f"**${row['value']:,.2f}**")
        color = "positive" if row["pnl_pct"] >= 0 else "negative"
        col5.markdown(f'<span class="{color}">{row["pnl_pct"]:+.2f}%</span>', unsafe_allow_html=True)
        if col6.button("🗑️", key=f"del_{i}"):
            st.session_state.holdings.pop(i)
            st.rerun()
        st.divider()

# ============================================================
# TRANSACTIONS
# ============================================================
elif page == "Transactions":
    st.title("🔄 Transactions")

    with st.expander("➕ Record Transaction", expanded=False):
        with st.form("add_tx"):
            tc1, tc2 = st.columns(2)
            t_symbol = tc1.text_input("Symbol").upper()
            t_name   = tc2.text_input("Name")
            tc3, tc4, tc5, tc6 = st.columns(4)
            t_type  = tc3.selectbox("Type", ["BUY", "SELL"])
            t_qty   = tc4.number_input("Quantity",     min_value=0.0, step=0.01)
            t_price = tc5.number_input("Price/Unit",   min_value=0.0, step=0.01)
            t_date  = tc6.date_input("Date")
            if st.form_submit_button("Record") and t_symbol:
                st.session_state.transactions.append({
                    "date": str(t_date), "symbol": t_symbol, "type": t_type,
                    "qty": t_qty, "price": t_price, "total": t_qty * t_price
                })
                st.success("Transaction recorded!")
                st.rerun()

    tx_df = pd.DataFrame(st.session_state.transactions)
    if not tx_df.empty:
        tx_df.columns = ["Date", "Symbol", "Type", "Qty", "Price", "Total"]
        st.dataframe(tx_df.style.format({
            "Price": "${:.2f}", "Total": "${:,.2f}"
        }), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions yet.")

# ============================================================
# AI ADVISOR
# ============================================================
elif page == "AI Advisor":
    st.title("🤖 AI Portfolio Advisor")

    api_key = st.sidebar.text_input("OpenAI API Key", type="password",
                                     help="Enter your OpenAI key to enable AI analysis")

    if not api_key:
        st.info("👈 Enter your OpenAI API key in the sidebar to start chatting with your AI advisor.")
        st.stop()

    client = OpenAI(api_key=api_key)

    df = get_df()
    portfolio_summary = df[["symbol", "name", "type", "qty", "avg_cost", "price", "value", "pnl_pct"]].to_dict(orient="records")

    system_prompt = f"""You are an expert investment portfolio advisor AI. 
The user's current portfolio data is:
{json.dumps(portfolio_summary, indent=2)}

Total portfolio value: ${df['value'].sum():,.2f}
Total P&L: ${df['pnl'].sum():,.2f} ({(df['pnl'].sum()/df['cost'].sum()*100):+.2f}%)

Help the user analyze their portfolio, suggest rebalancing strategies, identify risks, 
and provide investment insights. Always remind users this is not financial advice."""

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about your portfolio..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            messages = [{"role": "system", "content": system_prompt}] + st.session_state.chat_history
            stream = client.chat.completions.create(
                model="gpt-4o-mini", messages=messages, stream=True
            )
            response = st.write_stream(stream)

        st.session_state.chat_history.append({"role": "assistant", "content": response})

    if st.sidebar.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()
