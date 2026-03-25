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

# אתחול משתני מצב למחשבון הגמיש
if 'stock_price' not in st.session_state:
    st.session_state.stock_price = 1.0

# פונקציות סנכרון למחשבון הרכישה
def sync_all_from_inv():
    inv = st.session_state.inv_input
    shares = inv / st.session_state.stock_price
    st.session_state.inv_slider = inv
    st.session_state.shares_input = shares
    st.session_state.shares_slider = shares

def sync_all_from_shares():
    shares = st.session_state.shares_input
    inv = shares * st.session_state.stock_price
    st.session_state.shares_slider = shares
    st.session_state.inv_input = inv
    st.session_state.inv_slider = inv

def sync_all_from_inv_slider():
    inv = st.session_state.inv_slider
    shares = inv / st.session_state.stock_price
    st.session_state.inv_input = inv
    st.session_state.shares_input = shares
    st.session_state.shares_slider = shares

def sync_all_from_shares_slider():
    shares = st.session_state.shares_slider
    inv = shares * st.session_state.stock_price
    st.session_state.shares_input = shares
    st.session_state.inv_input = inv
    st.session_state.inv_slider = inv

@st.cache_data(ttl=300)
def get_sp500_data():
    sp500 = yf.Ticker("^GSPC")
    
    # משיכת היסטוריה מלאה לטובת מציאת שיא כל הזמנים
    hist_max = sp500.history(period="max")
    ath = hist_max['High'].max()
    
    # משיכת היסטוריה קצרה לטובת חישוב שינוי יומי (סגירה קודמת לעומת נוכחית)
    hist_recent = sp500.history(period="5d")
    current = hist_recent['Close'].iloc[-1]
    prev_close = hist_recent['Close'].iloc[-2]
    
    daily_change_points = current - prev_close
    daily_change_percent = (daily_change_points / prev_close) * 100
    
    return ath, current, daily_change_points, daily_change_percent

def get_stock_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="1d")['Close'].iloc[-1]
    except:
        return None

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- ממשק המשתמש ---
st.title("📈 מערכת ההשקעות של רענן - נירמול לשיא ה-S&P 500")

# משיכת נתוני S&P 500
with st.spinner('מושך נתוני S&P 500...'):
    sp500_ath, sp500_current, daily_pts, daily_pct = get_sp500_data()
    drop_percent = ((sp500_ath - sp500_current) / sp500_ath) * 100

# תצוגת נתוני מקרו (כולל שינוי יומי)
st.subheader("נתוני שוק (זמן אמת)")
col1, col2, col3 = st.columns(3)
col1.metric("S&P 500 נוכחי", f"{sp500_current:,.2f}", f"{daily_pts:,.2f} ({daily_pct:.2f}%)")
col2.metric("שיא כל הזמנים (ATH)", f"{sp500_ath:,.2f}")
col3.metric("מרחק מהשיא", f"-{drop_percent:.2f}%", delta_color="inverse")

# מערכת התראות
st.divider()
if drop_percent >= 20:
    st.error(f"🚨 שוק דובי! המדד ירד ב-{drop_percent:.1f}%. זוהי נקודת כניסה אגרסיבית על פי האסטרטגיה.")
elif drop_percent >= 10:
    st.warning(f"⚠️ תיקון בשוק. המדד ירד ב-{drop_percent:.1f}%. הזדמנות טובה להגדלת פוזיציות.")
elif drop_percent >= 5:
    st.info(f"💡 ירידה קלה של {drop_percent:.1f}%. כדאי לבחון רכישות נקודתיות.")
else:
    st.success("🟢 השוק קרוב לשיא כל הזמנים. רכישות כעת יהיו קרובות לשווי היעד המקורי.")

# אזור החישוב והרכישה
st.subheader("מחשבון רכישה גמיש")
col_input1, col_input2 = st.columns(2)

with col_input1:
    ticker = st.text_input("סימול מניה (לדוגמה MBLY, INTC):", value="MBLY").upper()
    target_value = st.number_input("שווי יעד רצוי בשיא (דולר):", min_value=1.0, value=10000.0)

with col_input2:
    if ticker:
        stock_price = get_stock_price(ticker)
        if stock_price:
            st.info(f"מחיר נוכחי של {ticker}: **${stock_price:,.2f}**")
            st.session_state.stock_price = stock_price
            
            # חישוב הערכים המומלצים לפי הנוסחה
            ratio = sp500_current / sp500_ath
            rec_inv = target_value * ratio
            rec_shares = rec_inv / stock_price
            
            # אתחול שדות העריכה בעת החלפת מניה
            if 'current_ticker' not in st.session_state or st.session_state.current_ticker != ticker:
                st.session_state.current_ticker = ticker
                st.session_state.inv_input = float(rec_inv)
                st.session_state.inv_slider = float(rec_inv)
                st.session_state.shares_input = float(rec_shares)
                st.session_state.shares_slider = float(rec_shares)
        else:
            st.error("לא ניתן למצוא את נתוני המניה. ודא שהסימול תקין.")

# אזור העריכה הגמישה (מוצג רק אם המניה חוקית)
if ticker and stock_price:
    st.write("---")
    st.write("🔧 **התאמה אישית של הרכישה:** כל שינוי באחד השדות (השקעה או מניות) יעדכן אוטומטית את השאר.")
    
    col_edit1, col_edit2 = st.columns(2)
    
    max_inv_slider = max(float(rec_inv * 3), 10000.0)
    max_shares_slider = max(float(rec_shares * 3), 1000.0)
    
    with col_edit1:
        st.number_input("השקעה בפועל ($):", min_value=0.0, step=10.0, key="inv_input", on_change=sync_all_from_inv)
        st.slider("סליידר השקעה ($):", min_value=0.0, max_value=max_inv_slider, step=10.0, key="inv_slider", on_change=sync_all_from_inv_slider, label_visibility="collapsed")
        
    with col_edit2:
        st.number_input("כמות מניות בפועל:", min_value=0.0, step=1.0, key="shares_input", on_change=sync_all_from_shares)
        st.slider("סליידר מניות:", min_value=0.0, max_value=max_shares_slider, step=1.0, key="shares_slider", on_change=sync_all_from_shares_slider, label_visibility="collapsed")

    # כפתור תיעוד רכישה עם הנתונים שעודכנו
    if st.button("📝 תעד רכישה זו בתיק (לפי הערכים למעלה)"):
        new_trade = pd.DataFrame([{
            'תאריך': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'סימול': ticker,
            'מחיר מניה': round(stock_price, 2),
            'כמות מניות': round(st.session_state.shares_input, 2),
            'סך השקעה': round(st.session_state.inv_input, 2),
            'מרחק S&P מהשיא': f"-{round(drop_percent, 2)}%"
        }])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_trade], ignore_index=True)
        st.success("הקנייה תועדה בהצלחה!")

# הצגת תיק הרכישות וייצוא נתונים
st.divider()
st.subheader("📚 היסטוריית רכישות")
if not st.session_state.portfolio.empty:
    st.dataframe(st.session_state.portfolio, use_container_width=True)
    
    total_invested = st.session_state.portfolio['סך השקעה'].sum()
    st.write(f"סך הכל השקעה עד כה: **${total_invested:,.2f}**")
    
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
