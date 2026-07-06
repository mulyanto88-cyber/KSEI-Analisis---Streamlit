import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os

# Set Konfigurasi Halaman
st.set_page_config(page_title="KSEI Advanced Market Intelligence Dashboard", layout="wide")

st.title("🚀 KSEI Advanced Market Intelligence Dashboard")
st.markdown("Dashboard analisis kepemilikan tingkat lanjut untuk mendeteksi pergerakan *Big Money*, tingkat akumulasi, dan korelasi harga saham.")

# Fungsi untuk memuat data
@st.cache_data
def load_data(shareholder_file, snapshot_file):
    df_sh = pd.read_csv(shareholder_file)
    df_sh['Date_parsed'] = pd.to_datetime(df_sh['Date'], format='%d/%m/%Y', errors='coerce')
    df_sh['Date_norm'] = df_sh['Date_parsed'].dt.strftime('%Y-%m-%d')
    
    df_sn = pd.read_csv(snapshot_file)
    df_sn['DATE_parsed'] = pd.to_datetime(df_sn['DATE'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_sn['Date_norm'] = df_sn['DATE_parsed'].dt.strftime('%Y-%m-%d')
    return df_sh, df_sn

# Sidebar - Data Source
st.sidebar.header("📁 Data Source")
sh_default = "KSEI_Shareholder_Pure_KSEI_OK.csv"
sn_default = "KSE_1Persen_Monthly_Snapshot_OK.csv"

uploaded_sh = st.sidebar.file_uploader("Upload Shareholder Pure KSEI CSV", type=["csv"])
uploaded_sn = st.sidebar.file_uploader("Upload 1% Monthly Snapshot CSV", type=["csv"])

file_sh_path = uploaded_sh if uploaded_sh is not None else (sh_default if os.path.exists(sh_default) else None)
file_sn_path = uploaded_sn if uploaded_sn is not None else (sn_default if os.path.exists(sn_default) else None)

if not file_sh_path or not file_sn_path:
    st.warning("⚠️ Silakan upload atau letakkan kedua file CSV di folder aplikasi.")
    st.stop()

df_sh, df_sn = load_data(file_sh_path, file_sn_path)

ksei_labels = {
    'IS': 'Insurance', 'CP': 'Corporate', 'PF': 'Pension Fund', 
    'IB': 'Investment Bank', 'ID': 'Individual (Retail)', 'MF': 'Mutual Fund', 
    'SC': 'Securities Co.', 'FD': 'Foundation', 'OT': 'Others'
}

# Sidebar - Filter Saham
ticker_list = sorted(df_sh['Code'].unique())
selected_ticker = st.sidebar.selectbox("🎯 Pilih Kode Saham (Ticker):", ticker_list, index=ticker_list.index('AADI') if 'AADI' in ticker_list else 0)

# Pemrosesan Data per Ticker
df_sh_ticker = df_sh[df_sh['Code'] == selected_ticker].sort_values('Date_parsed').copy()
df_sn_ticker = df_sn[df_sn['SHARE_CODE'] == selected_ticker].sort_values('DATE_parsed').copy()

# Perhitungan Metrics Tambahan Tingkat Lanjut (Advanced Feature)
if not df_sh_ticker.empty:
    df_sh_ticker['Price_Return_Pct'] = df_sh_ticker['Price'].pct_change() * 100
    
    # Pengelompokan Big Money (Institusi) vs Retail
    inst_local = ['Local_IS', 'Local_CP', 'Local_PF', 'Local_IB', 'Local_MF', 'Local_SC']
    inst_foreign = ['Foreign_IS', 'Foreign_CP', 'Foreign_PF', 'Foreign_IB', 'Foreign_MF', 'Foreign_SC']
    
    df_sh_ticker['Big_Money_Vol'] = df_sh_ticker[inst_local + inst_foreign].sum(axis=1)
    df_sh_ticker['Retail_Vol'] = df_sh_ticker['Local_ID'] + df_sh_ticker['Foreign_ID']
    df_sh_ticker['Big_Money_Chg'] = df_sh_ticker['Big_Money_Vol'].diff()
    
    # Hitung Herfindahl-Hirschman Index (HHI) dari Data Snapshot 1% untuk mengukur Konsentrasi Bandar
    hhi_list = []
    for date in df_sh_ticker['Date_norm']:
        snap_date = df_sn_ticker[df_sn_ticker['Date_norm'] == date]
        if not snap_date.empty:
            # HHI = jumlah dari kuadrat persentase kepemilikan
            hhi = np.sum(snap_date['PERCENTAGE'] ** 2)
            hhi_list.append(hhi)
        else:
            hhi_list.append(np.nan)
    df_sh_ticker['HHI_Index'] = hhi_list

# Layout Tab Baru Lebih Komprehensif
tab1, tab2, tab3 = st.tabs(["📊 Market Structure & Big Money Tracking", "🦅 Top 1% Whales Analysis", "🔬 Quant Correlation Matrix"])

# --- TAB 1: MARKET STRUCTURE & BIG MONEY ---
with tab1:
    st.subheader(f"Analisis Pergerakan Big Money & Struktur Kepemilikan: {selected_ticker}")
    if df_sh_ticker.empty:
        st.write("Data Kosong")
    else:
        latest = df_sh_ticker.iloc[-1]
        prev = df_sh_ticker.iloc[-2] if len(df_sh_ticker) > 1 else latest
        
        # Row 1: KPI Blocks dengan Delta Perubahan
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Harga Terakhir", f"Rp {latest['Price']:,}", f"{latest['Price_Return_Pct']:.2f}%" if not pd.isna(latest['Price_Return_Pct']) else "0%")
        
        bm_pct = (latest['Big_Money_Vol'] / latest['Total_Shares']) * 100
        bm_delta = ((latest['Big_Money_Vol'] - prev['Big_Money_Vol']) / prev['Total_Shares']) * 100 if len(df_sh_ticker) > 1 else 0
        c2.metric("Porsi Big Money (Institusi)", f"{bm_pct:.2f} %", f"{bm_delta:+.2f}% MoM")
        
        ret_pct = (latest['Retail_Vol'] / latest['Total_Shares']) * 100
        ret_delta = ((latest['Retail_Vol'] - prev['Retail_Vol']) / prev['Total_Shares']) * 100 if len(df_sh_ticker) > 1 else 0
        c3.metric("Porsi Ritel (Individual)", f"{ret_pct:.2f} %", f"{ret_delta:+.2f}% MoM")
        
        # Interpretasi HHI
        hhi_val = latest['HHI_Index'] if not pd.isna(latest['HHI_Index']) else 0
        hhi_status = "Sangat Terkonsentrasi (Aman/Bandar Dominan)" if hhi_val > 1500 else "Terdistribusi (Ritel Dominan)"
        c4.metric("Indeks Konsentrasi (HHI)", f"{hhi_val:,.1f}", hhi_status, delta_color="off")
        
        st.markdown("---")
        
        # Chart Dual Axis: Perubahan Kepemilikan Big Money vs Perubahan Harga
        st.markdown("### 📈 Tren Akumulasi Big Money vs Harga Saham")
        fig_bm = go.Figure()
        fig_bm.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Big_Money_Vol'], name='Volume Big Money', mode='lines+markers', line=dict(color='#1f77b4', width=4), yaxis='y'))
        fig_bm.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Price'], name='Harga Saham', mode='lines+markers', line=dict(color='#ff7f0e', width=3, dash='dash'), yaxis='y2'))
        
        fig_bm.update_layout(
            xaxis=dict(title='Periode Bulanan'),
            yaxis=dict(title='Total Saham Institusi (Lembar)', showgrid=False),
            yaxis2=dict(title='Harga Saham (Rp)', overlaying='y', side='right', showgrid=True),
            legend=dict(orientation="h", y=1.1, x=0)
        )
        st.plotly_chart(fig_bm, use_container_width=True)

        # Analisis Top Buyer & Seller Sektoral Bulan Ini
        st.markdown("### 🕵️ Penggerak Utama Bulan Ini (Top Player)")
        cc1, cc2 = st.columns(2)
        with cc1:
            st.info(f"🏆 **Top Net Buyer Bulan Ini:** {latest['Top_Buyer']} (Value: Rp {latest['Top_Buyer_Val']:,.0f})")
        with cc2:
            st.danger(f"🚨 **Top Net Seller Bulan Ini:** {latest['Top_Seller']} (Value: Rp {latest['Top_Seller_Val']:,.0f})")

# --- TAB 2: WHALES ANALYSIS (1%) ---
with tab2:
    st.subheader(f"Analisis Kepemilikan Whales / Konglomerasi (>= 1%)")
    if df_sn_ticker.empty:
        st.info("Data snapshot tidak tersedia.")
    else:
        dates = sorted(df_sn_ticker['Date_norm'].unique())
        selected_d = st.selectbox("📅 Pilih Bulan Evaluasi Whales:", dates, index=len(dates)-1)
        
        df_selected_snap = df_sn_ticker[df_sn_ticker['Date_norm'] == selected_d].sort_values('PERCENTAGE', ascending=False)
        
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            fig_whales = px.bar(
                df_selected_snap.head(10), x='PERCENTAGE', y='INVESTOR_NAME', orientation='h',
                title=f"Top 10 Pemegang Saham Terbesar ({selected_d})",
                color='INVESTOR_TYPE', labels={'INVESTOR_NAME':'Nama Entitas/Investor', 'PERCENTAGE':'Porsi (%)'}
            )
            fig_whales.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_whales, use_container_width=True)
            
        with col_s2:
            st.markdown("#### 🏛️ Dominasi Tipe Entitas Whales")
            df_type_summary = df_selected_snap.groupby('INVESTOR_TYPE')['PERCENTAGE'].sum().reset_index()
            fig_pie_type = px.pie(df_type_summary, values='PERCENTAGE', names='INVESTOR_TYPE', hole=0.4)
            st.plotly_chart(fig_pie_type, use_container_width=True)

# --- TAB 3: QUANT CORRELATION MATRIX ---
with tab3:
    st.subheader("🔬 Quant Analysis: Korelasi & Scatter Matrix")
    if len(df_sh_ticker) < 3:
        st.warning("⚠️ Data historis bulanan terlalu pendek untuk membuat pemodelan regresi OLS trendline yang valid (Minimal butuh 3 bulan).")
    else:
        # Menghitung korelasi khusus untuk semua kategori perubahan volume terhadap return harga saham ini
        chg_vol_cols = [c for c in df_sh_ticker.columns if c.endswith('_Chg_Vol')]
        corr_matrix = df_sh_ticker[chg_vol_cols + ['Price_Return_Pct']].corr()
        
        price_corr = corr_matrix['Price_Return_Pct'].drop('Price_Return_Pct').sort_values(ascending=False).reset_index()
        price_corr.columns = ['Kategori KSEI', 'Korelasi Koefisien']
        
        # Beri label yang cantik
        price_corr['Nama Kategori'] = price_corr['Kategori KSEI'].apply(lambda x: f"{'Lokal' if 'Local' in x else 'Asing'} - {ksei_labels.get(x.split('_')[1], x.split('_')[1])}")
        
        st.markdown("### Hubungan Linear Perubahan Volume Investor vs Return Saham")
        fig_corr_bar = px.bar(
            price_corr, x='Korelasi Koefisien', y='Nama Kategori', orientation='h',
            title=f"Kategori Investor Mana yang Paling Menggerakkan Harga {selected_ticker}?",
            color='Korelasi Koefisien', color_continuous_scale=px.colors.diverging.Tealrose
        )
        fig_corr_bar.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_corr_bar, use_container_width=True)
        
        # Scatter Plot dengan Statsmodels OLS Trendline terjamin aman
        st.markdown("### 📊 Pola Distribusi & OLS Trendline Regresi")
        target_investor = st.selectbox("Pilih Kategori Investor untuk visualisasi sebaran:", price_corr['Kategori KSEI'].tolist())
        
        clean_target_name = price_corr[price_corr['Kategori KSEI'] == target_investor]['Nama Kategori'].values[0]
        
        fig_scat = px.scatter(
            df_sh_ticker.dropna(subset=['Price_Return_Pct']),
            x=target_investor, y='Price_Return_Pct',
            trendline="ols", text='Date_norm',
            title=f"Analisis Regresi: Perubahan Volume {clean_target_name} vs Return Harga",
            labels={target_investor: 'Perubahan Volume Transaksi (Lembar)', 'Price_Return_Pct': 'Return Harga Saham (%)'}
        )
        st.plotly_chart(fig_scat, use_container_width=True)
