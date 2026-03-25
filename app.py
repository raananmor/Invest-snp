import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from google.oauth2 import service_account
import io

# הגדרת הדף
st.set_page_config(page_title="מערכת השקעות מנורמלת", layout="wide")

# הגדרות Google Drive
DRIVE_FILE_NAME = "invest_snp.csv"

# --- פונקציות לאימות וגישה ל-Drive עם מנגנון שגיאות ---
@st.cache_resource
def get_drive_service():
    """מנסה להתחבר ל-Drive. מחזיר את השירות או הודעת שגיאה מפורטת."""
    try:
        if "gdrive_service_account" not in st.secrets:
            return None, "ההגדרה 'gdrive_service_account' לא קיימת ב-Streamlit Secrets."
        
        creds_dict = json.loads(st.secrets["gdrive_service_account"])
        creds = service_account.Credentials.from_service_account_info(creds_dict)
        service = build('drive', 'v3', credentials=creds)
        return service, None
    except Exception as e:
        return None, f"שגיאת התחברות ל-Drive: {str(e)}"

def find_file_in_drive(service, filename):
    results = service.files().list(
        q=f"name='{filename}' and trashed=false",
        spaces='drive',
        fields='files(id, name)').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    return None

def load_data_from_drive(service):
    """מנסה לטעון נתונים מה-Drive. מחזיר DataFrame והודעת שגיאה אם יש."""
    try:
        file_id = find_file_in_drive(service, DRIVE_FILE_NAME)
        if not file_id:
            return pd.DataFrame(columns=[
                'תאריך', 'סימול', 'מחיר מניה', 'כמות מניות', 'סך השקעה', 'מרחק S&P מהשיא'
            ]), "קובץ לא נמצא ב-Drive. נוצר תיק חדש."

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        fh.seek(0)
        return pd.read_csv(fh, encoding='utf-8-sig'), None
    except Exception as e:
        return None, f"שגיאה בקריאת הקובץ מה-Drive: {str(e)}"

def save_data_to_drive(service, df):
    """מנסה לשמור נתונים ל-Drive."""
    try:
        file_id = find_file_in_drive(service, DRIVE_FILE_NAME)
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        fh = io.BytesIO(csv_data)
        media = MediaFileUpload(DRIVE_FILE_NAME, mimetype='text/csv', resumable=True)

        if file_id:
            service.files().update(fileId=file_id, media_body=media).execute()
        else:
            file_metadata = {'name': DRIVE_FILE_NAME, 'parents': ['root']}
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return True, None
    except Exception as e:
        return False, f"שגיאה בשמירת הקובץ ל-Drive: {str(e)}"

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8-sig')

# --- אתחול המערכת וקביעת "מצב בטוח" ---
drive_service, connection_error = get_drive_service()
use_drive = drive_service is not None

# אתחול התיק ב-Session State
if 'portfolio' not in st.session_state:
    if use_drive:
        df, load_error = load_data_from_drive(drive_service)
        if df is not None:
            st.session_state.portfolio = df
            if load_error: # מקרה שבו הקובץ פשוט לא קיים עדיין (לא שגיאה קריטית)
                st.info(load_error)
        else:
            # קריסה בקריאה מה-Drive - מעבר למצב בטוח
            use_drive = False
            connection_error = load_error
            st.session_state.portfolio = pd.DataFrame(columns=[
                'תאריך', 'סימול', 'מחיר מניה', 'כמות מניות', 'סך השקעה', 'מרחק S&P מהשיא'
            ])
    else:
        st.session_state.portfolio = pd.DataFrame(columns=[
            'תאריך', 'סימול', 'מחיר מניה', 'כמות מניות', 'סך השקעה', 'מרחק S&P מהשיא'
        ])

# --- פונקציות סנכרון للمחשבון ---
if 'stock_price' not in st.session_state:
    st.session_state.stock_price = 1.0

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

# --- משיכת נתוני השוק ---
@st.cache_data(ttl=300)
def get_sp500_data():
    sp500 = yf.Ticker("^GSPC")
    hist_max = sp500.history(period="max")
    ath = hist_max['High'].max()
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

# --- ממשק המשתמש ---
st.title("📈 מערכת ההשקעות של רענן")

# התראת מצב בטוח
if not use_drive:
    st.warning(f"⚠️ **המערכת פועלת במצב בטוח (מקומי)**. נתוני התיק נשמרים זמנית ולא מסונכרנים לענן.\n\n**פרטי השגיאה:** {connection_error}")
else:
    st.success("☁️ מחובר ל-Google Drive ומסונכרן.")

# משיכת נתוני S&P 500
with st.spinner('מושך נתוני S&P 500...'):
    sp500_ath, sp500_current, daily_pts, daily_pct = get_sp500_data()
    drop_percent = ((sp500_ath - sp500_current) / sp500_ath) * 100

st.subheader("נתוני שוק (זמן אמת)")
col1, col2, col3 = st.columns(3)
col1.metric("S&P 500 נוכחי", f"{sp500_current:,.2f}", f"{daily_pts:,.2f} ({daily_pct:.2f}%)")
col2.metric("שיא כל הזמנים (ATH)", f"{sp500_ath:,.2f}")
col3.metric("מרחק מהשיא", f"-{drop_percent:.2f}%", delta_color="inverse")

# מחשבון הרכישה
st.subheader("מחשבון רכישה גמיש ומנורמל")
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
            
            ratio = sp500_current / sp500_ath
            rec_inv = target_value * ratio
            rec_shares = rec_inv / stock_price
            
            if 'current_ticker' not in st.session_state or st.session_state.current_ticker != ticker:
                st.session_state.current_ticker = ticker
                st.session_state.inv_input = float(rec_inv)
                st.session_state.inv_slider = float(rec_inv)
                st.session_state.shares_input = float(rec_shares)
                st.session_state.shares_slider = float(rec_shares)
        else:
            st.error("לא ניתן למצוא את נתוני המניה. ודא שהסימול תקין.")

# עריכה והוספה לתיק
if ticker and stock_price:
    st.write("---")
    st.write(f"💡 הנתונים המנורמלים המחושבים מוצגים כסמלי דלתא (Delta) להשוואה מול הבחירה שלך.")
    
    col_edit1, col_edit2 = st.columns(2)
    max_inv_slider = max(float(rec_inv * 2), 5000.0)
    max_shares_slider = max(float(rec_shares * 2), 500.0)
    
    with col_edit1:
        st.metric(label="השקעה בפועל ($)", value=f"${st.session_state.inv_input:,.2f}", delta=f"${rec_inv:,.2f} (מנורמל)")
        st.number_input("השקעה בפועל ($):", min_value=0.0, step=10.0, key="inv_input", on_change=sync_all_from_inv, label_visibility="collapsed")
        st.slider("סליידר השקעה ($):", min_value=0.0, max_value=max_inv_slider, step=10.0, key="inv_slider", on_change=sync_all_from_inv_slider)
        
    with col_edit2:
        st.metric(label="כמות מניות בפועל", value=f"{st.session_state.shares_input:,.2f}", delta=f"{rec_shares:,.2f} (מנורמל)")
        st.number_input("כמות מניות בפועל:", min_value=0.0, step=1.0, key="shares_input", on_change=sync_all_from_shares, label_visibility="collapsed")
        st.slider("סליידר מניות:", min_value=0.0, max_value=max_shares_slider, step=1.0, key="shares_slider", on_change=sync_all_from_shares_slider)

    button_label = "📝 תעד רכישה ב-Drive" if use_drive else "📝 תעד רכישה מקומית (מצב בטוח)"
    
    if st.button(button_label):
        new_trade = pd.DataFrame([{
            'תאריך': datetime.now().strftime("%Y-%m-%d %H:%M"),
            'סימול': ticker,
            'מחיר מניה': round(stock_price, 2),
            'כמות מניות': round(st.session_state.shares_input, 2),
            'סך השקעה': round(st.session_state.inv_input, 2),
            'מרחק S&P מהשיא': f"-{round(drop_percent, 2)}%"
        }])
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_trade], ignore_index=True)
        
        if use_drive:
            success, save_err = save_data_to_drive(drive_service, st.session_state.portfolio)
            if success:
                st.success("נשמר בהצלחה ב-Drive!")
            else:
                st.error(f"השמירה בענן נכשלה. הנתונים נשמרו מקומית. שגיאה: {save_err}")
                use_drive = False # מעבר למצב בטוח להמשך העבודה
        else:
            st.success("הקנייה תועדה מקומית בזיכרון המערכת.")

# תצוגת התיק ואפשרות ייצוא
st.divider()
st.subheader("📚 היסטוריית רכישות")
if not st.session_state.portfolio.empty:
    st.dataframe(st.session_state.portfolio, use_container_width=True)
    
    total_invested = st.session_state.portfolio['סך השקעה'].sum()
    st.write(f"סך הכל השקעה בתיק: **${total_invested:,.2f}**")
    
    # תמיד נאפשר הורדה מקומית כגיבוי, אבל נדגיש אותה במיוחד במצב בטוח
    st.write("---")
    if not use_drive:
        st.info("💡 כיוון שהמערכת במצב בטוח, מומלץ להוריד את הקובץ בסיום כדי לא לאבד את התיעוד.")
        
    csv = convert_df_to_csv(st.session_state.portfolio)
    st.download_button(
        label="📥 הורד את תיק ההשקעות למחשב (CSV)",
        data=csv,
        file_name='portfolio_history_backup.csv',
        mime='text/csv',
    )
else:
    st.write("טרם תועדו רכישות בתיק.")
