import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# הגדרת הדף
st.set_page_config(page_title="מערכת השקעות מנורמלת", layout="wide")

# אתחול מסד נתונים זמני (Session State) לתיעוד הרכישות
if 'portfolio' not in st.session_state:
    st.session_state.portfolio = pd.DataFrame(columns=[
        'תאריך', 'סימול', 'מחיר מניה', 'כמות מניות', 'סך השקעה', 'מרחק S&P מהשיא'
    ])

@st.cache_data(ttl=300)
def get_sp500_data():
    sp500 = yf.Ticker("^GSPC")
    hist = sp500.history(period="max")
    ath = hist['High'].max()
    current = hist['Close'].iloc[-1]
    return ath, current

def get_stock_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="1d")['Close'].iloc[-1]
    except:
        return None

@st.cache_data
def convert_df_to_csv(df):
    # קידוד מתאים לאקסל בעברית
    return df.to_csv(index=False).encode('utf-8-sig')

# --- ממשק המשתמש ---
st.title("📈 מערכת ההשקעות של רענן - נירמול לשיא ה-S&P 500")

# משיכת נתוני S&P 500
with st.spinner('מושך נתוני S&P 500...'):
    sp500_ath, sp500_current = get_sp500_data()
    drop_percent = ((sp500_ath - sp500_current) / sp500_ath) * 100

# תצוגת נתוני מקרו
st.subheader("נתוני שוק (זמן אמת)")
col1, col2, col3 = st.columns(3)
col1.metric("S&P 500 נוכחי", f"{sp500_current:,.2f}")
col2.metric("שיא כל הזמנים (ATH)", f"{sp500_ath:,.2f}")
col3.metric("מרחק מהשיא", f"-{drop_percent:.2f}%", delta_color="inverse")

# מערכת התראות (Triggers) לקנייה
st.divider()
if drop_percent >= 20:
    st.error(f"🚨 שוק דובי! המדד ירד ב-{drop_percent:.1f}%. זוהי נקודת כניסה אגרסיבית על פי האסטרטגיה.")
elif drop_percent >= 10:
    st.warning(f"⚠️ תיקון בשוק. המדד ירד ב-{drop_percent:.1f}%. הזדמנות טובה להגדלת פוזיציות.")
elif drop_percent >= 5:
    st.info(f"💡 ירידה קלה של {drop_percent:.1f}%. כדאי לבחון רכישות נקודתיות.")
else:
    st.success("🟢 השוק קרוב לשיא כל הזמנים. רכישות כעת יהיו קרובות לשווי היעד המקורי.")

# אזור חישוב ורכישה
st.subheader("מחשבון רכישה ותיעוד")
col_input1, col_input2 = st.columns(2)

with col_input1:
    ticker = st.text_input("סימול מניה (לדוגמה MBLY, INTC):", value="MBLY").upper()
    target_value = st.number_input("שווי יעד רצוי בשיא (דולר):", min_value=1.0, value=10000.0)

with col_input2:
    if ticker:
        stock_price = get_stock_price(ticker)
        if stock_price:
            st.info(f"מחיר נוכחי של {ticker}: **${stock_price:,.2f}**")
            
            # החישוב המתמטי
            ratio = sp500_current / sp500_ath
            investment_needed = target_value * ratio
            shares_to_buy = investment_needed / stock_price
            
            st.write(f"השקעה נדרשת כעת: **${investment_needed:,.2f}**")
            st.write(f"כמות מניות לרכישה: **{shares_to_buy:,.2f}**")
            
            # כפתור תיעוד רכישה
            if st.button("📝 תעד רכישה זו בתיק"):
                new_trade = pd.DataFrame([{
                    'תאריך': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'סימול': ticker,
                    'מחיר מניה': round(stock_price, 2),
                    'כמות מניות': round(shares_to_buy, 2),
                    'סך השקעה': round(investment_needed, 2),
                    'מרחק S&P מהשיא': f"-{round(drop_percent, 2)}%"
                }])
                st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_trade], ignore_index=True)
                st.success("הקנייה תועדה בהצלחה!")
        else:
            st.error("לא ניתן למצוא את נתוני המניה. ודא שהסימול תקין.")

# הצגת תיק הרכישות וייצוא נתונים
st.divider()
st.subheader("📚 היסטוריית רכישות")
if not st.session_state.portfolio.empty:
    st.dataframe(st.session_state.portfolio, use_container_width=True)
    
    total_invested = st.session_state.portfolio['סך השקעה'].sum()
    st.write(f"סך הכל השקעה עד כה: **${total_invested:,.2f}**")
    
    # --- כפתור הייצוא החדש ---
    st.write("---")
    csv = convert_df_to_csv(st.session_state.portfolio)
    st.download_button(
        label="📥 הורד את תיק ההשקעות לאקסל (CSV)",
        data=csv,
        file_name='portfolio_history.csv',
        mime='text/csv',
    )
else:
    st.write("טרם תועדו רכישות במערכת. הכנס סימול, חשב ולחץ על 'תעד רכישה'.")
    
