import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os

# Konfigurasi Utama Aplikasi
st.set_page_config(page_title="Smart Money & Bandarmologi Command Center", layout="wide")

st.title("🛰️ Smart Money & Bandarmologi Command Center")
st.markdown("Sistem Radar & Screening Kepemilikan KSEI untuk Mendeteksi Akumulasi Institusi, Active Funds, dan Asing.")

# Sistem Caching Data Berkinerja Tinggi
@st.cache_data
def load_and_process_data(shareholder_file, snapshot_file):
    # 1. Proses Data Shareholder (Makro)
    df_sh = pd.read_csv(shareholder_file)
    df_sh['Date_parsed'] = pd.to_datetime(df_sh['Date'], format='%d/%m/%Y', errors='coerce')
    df_sh['Date_norm'] = df_sh['Date_parsed'].dt.strftime('%Y-%m-%d')
    
    # Kelompokkan Smart Money vs Retail
    funds_cols = ['Local_MF', 'Foreign_MF']  # Mutual/Active Funds & ETF
    corp_cols = ['Local_CP', 'Foreign_CP']    # Corporate / Pengendali
    inst_cols = ['Local_IS', 'Local_PF', 'Local_IB', 'Local_SC', 'Foreign_IS', 'Foreign_PF', 'Foreign_IB', 'Foreign_SC']
    
    df_sh['Smart_Money_Vol'] = df_sh[funds_cols + corp_cols + inst_cols].sum(axis=1)
    df_sh['Active_Funds_Vol'] = df_sh[funds_cols].sum(axis=1)
    df_sh['Corporate_Vol'] = df_sh[corp_cols].sum(axis=1)
    df_sh['Retail_Vol'] = df_sh['Local_ID'] + df_sh['Foreign_ID']
    
    # Net Flow Nilai (Value) Rupiah
    df_sh['Smart_Money_Net_Val'] = df_sh[['Local_MF_Chg_Val', 'Foreign_MF_Chg_Val', 'Local_CP_Chg_Val', 'Foreign_CP_Chg_Val',
                                          'Local_IS_Chg_Val', 'Local_PF_Chg_Val', 'Local_IB_Chg_Val', 'Local_SC_Chg_Val',
                                          'Foreign_IS_Chg_Val', 'Foreign_PF_Chg_Val', 'Foreign_IB_Chg_Val', 'Foreign_SC_Chg_Val']].sum(axis=1)
    df_sh['Active_Funds_Net_Val'] = df_sh[['Local_MF_Chg_Val', 'Foreign_MF_Chg_Val']].sum(axis=1)
    df_sh['Retail_Net_Val'] = df_sh['Local_ID_Chg_Val'] + df_sh['Foreign_ID_Chg_Val']
    
    # 2. Proses Data Snapshot 1% (Mikro Whales)
    df_sn = pd.read_csv(snapshot_file)
    df_sn['DATE_parsed'] = pd.to_datetime(df_sn['DATE'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_sn['Date_norm'] = df_sn['DATE_parsed'].dt.strftime('%Y-%m-%d')
    
    return df_sh, df_sn

# Integrasi File Otomatis / Manual Upload
st.sidebar.header("📁 Data Source Pipeline")
sh_default = "KSEI_Shareholder_Pure_KSEI_OK.csv"
sn_default = "KSE_1Persen_Monthly_Snapshot_OK.csv"

uploaded_sh = st.sidebar.file_uploader("Upload Shareholder Pure KSEI CSV", type=["csv"])
uploaded_sn = st.sidebar.file_uploader("Upload 1% Monthly Snapshot CSV", type=["csv"])

file_sh_path = uploaded_sh if uploaded_sh is not None else (sh_default if os.path.exists(sh_default) else None)
file_sn_path = uploaded_sn if uploaded_sn is not None else (sn_default if os.path.exists(sn_default) else None)

if not file_sh_path or not file_sn_path:
    st.warning("⚠️ Menunggu pipeline data... Pastikan file CSV diletakkan di direktori yang sama atau silakan upload via sidebar.")
    st.stop()

# Eksekusi Data Loader
df_sh, df_sn = load_and_process_data(file_sh_path, file_sn_path)

# Dictionary Labeling KSEI
ksei_labels = {
    'IS': 'Insurance', 'CP': 'Corporate', 'PF': 'Pension Fund', 
    'IB': 'Investment Bank', 'ID': 'Individual (Retail)', 'MF': 'Mutual Fund / ETF', 
    'SC': 'Securities Co.', 'FD': 'Foundation', 'OT': 'Others'
}

# Deklarasi Tab Utama Kontrol
tab1, tab2, tab3 = st.tabs(["🛰️ Smart Money Radar (Screener)", "🔍 Ticker Bandarmologi Flow", "🐳 Whales Identity Tracking"])

# ==========================================
# --- TAB 1: SMART MONEY RADAR (SCREENER) ---
# ==========================================
with tab1:
    st.subheader("Sistem Penyaringan Saham Berdasarkan Pola Akumulasi")
    st.markdown("Gunakan panel ini untuk menyaring saham secara instan di mana **Funds/Corporate melakukan akumulasi besar** sementara **Retail sedang jualan (distribusi/cutloss)**.")
    
    # Filter Kondisi Pasar pada Bulan Terakhir
    latest_market_date = df_sh['Date_norm'].max()
    df_market_latest = df_sh[df_sh['Date_norm'] == latest_market_date].copy()
    
    # Kontrol Parameter Screener
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        min_price = st.number_input("Harga Minimum (Rp)", min_value=0, value=100, step=50)
    with col_f2:
        smart_money_filter = st.selectbox("Fokus Utama Aliran Dana:", ["Active Funds & ETF Only", "Total Smart Money (Funds + Corp + Inst)"])
    with col_f3:
        retail_condition = st.checkbox("Hanya Tampilkan Saat Ritel Net SELL (Good Sign)", value=True)
        
    # Kalkulasi Logika Filter Kuantitatif
    df_screened = df_market_latest[df_market_latest['Price'] >= min_price].copy()
    
    if smart_money_filter == "Active Funds & ETF Only":
        df_screened['Selected_Net_Val'] = df_screened['Active_Funds_Net_Val']
    else:
        df_screened['Selected_Net_Val'] = df_screened['Smart_Money_Net_Val']
        
    if retail_condition:
        df_screened = df_screened[df_screened['Retail_Net_Val'] < 0]
        
    # Urutkan berdasarkan Net Buy Dana Terbesar
    df_screened = df_screened.sort_values(by='Selected_Net_Val', ascending=False).reset_index(drop=True)
    
    # Tampilan Hasil Radar Table
    st.markdown(f"### 🎯 Hasil Analisis Screening Pasar per Tanggal Data Terakhir: `{latest_market_date}`")
    
    display_cols = ['Code', 'Price', 'Selected_Net_Val', 'Retail_Net_Val', 'Top_Buyer', 'Top_Seller']
    df_display = df_screened[display_cols].rename(columns={
        'Code': 'Ticker',
        'Price': 'Harga Terakhir',
        'Selected_Net_Val': 'Net Flow Smart Money (IDR)',
        'Retail_Net_Val': 'Net Flow Ritel (IDR)',
        'Top_Buyer': 'Kategori Pembeli Utama',
        'Top_Seller': 'Kategori Penjual Utama'
    })
    
    st.dataframe(
        df_display.style.format({
            'Net Flow Smart Money (IDR)': '{:,.0f}',
            'Net Flow Ritel (IDR)': '{:,.0f}',
            'Harga Terakhir': 'Rp {:,}'
        }),
        use_container_width=True,
        column_config={
            "Net Flow Smart Money (IDR)": st.column_config.NumberColumn(format="Rp %,.0f"),
            "Net Flow Ritel (IDR)": st.column_config.NumberColumn(format="Rp %,.0f"),
        }
    )

# ==========================================
# --- TAB 2: TICKER BANDARMOLOGI FLOW ---
# ==========================================
with tab2:
    ticker_list = sorted(df_sh['Code'].unique())
    selected_ticker = st.selectbox("🎯 Pilih Kode Saham untuk Analisis Mendalam:", ticker_list, index=ticker_list.index('AADI') if 'AADI' in ticker_list else 0)
    
    df_sh_ticker = df_sh[df_sh['Code'] == selected_ticker].sort_values('Date_parsed').copy()
    df_sn_ticker = df_sn[df_sn['SHARE_CODE'] == selected_ticker].sort_values('DATE_parsed').copy()
    
    if df_sh_ticker.empty:
        st.error("Data tidak ditemukan.")
    else:
        df_sh_ticker['Price_Return_Pct'] = df_sh_ticker['Price'].pct_change() * 100
        
        # Hitung HHI untuk Ticker Terpilih
        hhi_list = []
        for date in df_sh_ticker['Date_norm']:
            snap_date = df_sn_ticker[df_sn_ticker['Date_norm'] == date]
            hhi = np.sum(snap_date['PERCENTAGE'] ** 2) if not snap_date.empty else np.nan
            hhi_list.append(hhi)
        df_sh_ticker['HHI_Index'] = hhi_list
        
        latest = df_sh_ticker.iloc[-1]
        prev = df_sh_ticker.iloc[-2] if len(df_sh_ticker) > 1 else latest
        
        # Status Detektor Kekuatan Akumulasi
        st.markdown("### 🚦 Status Detektor Bandarmologi")
        sd1, sd2, sd3 = st.columns(3)
        
        # Aturan Logika Klasifikasi Status
        smart_flow = latest['Smart_Money_Net_Val']
        retail_flow = latest['Retail_Net_Val']
        
        if smart_flow > 0 and retail_flow < 0:
            status_bandar = "🔥 AKUMULASI MASIF (Big Money Masuk / Ritel Keluar)"
            color_box = st.success
        elif smart_flow > 0 and retail_flow > 0:
            status_bandar = "⚖️ PARTISIPASI PUBLIK (Kedua Pihak Akumulasi)"
            color_box = st.info
        elif smart_flow < 0 and retail_flow > 0:
            status_bandar = "🚨 DISTRIBUSI (Big Money Jualan / Ritel Tampung)"
            color_box = st.error
        else:
            status_bandar = "📉 MARK DOWN (Fase Penurunan Sunyi)"
            color_box = st.warning
            
        color_box(f"**Kondisi Tren Saat Ini:** {status_bandar}")
        
        # Tampilan Grafik Intuitif Komparasi Kumulatif Flow vs Harga
        st.markdown("### 📊 Pola Aliran Dana Kumulatif Terhadap Harga")
        
        fig_cum = go.Figure()
        # Garis Volume Kepemilikan Active Funds / ETF
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Active_Funds_Vol'], name='Volume Active Funds & ETF', line=dict(color='#00CC96', width=4)))
        # Garis Volume Ritel
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Retail_Vol'], name='Volume Ritel (Individual)', line=dict(color='#EF553B', width=2, dash='dot')))
        # Sumbu Kanan: Harga Saham
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Price'], name='Harga Saham (Rp)', line=dict(color='#AB63FA', width=3), yaxis='y2'))
        
        fig_cum.update_layout(
            title=f"Perbandingan Pergerakan Dana Active Funds vs Ritel Pada Saham {selected_ticker}",
            xaxis=dict(title='Bulan'),
            yaxis=dict(title='Jumlah Saham (Lembar)', showgrid=False),
            yaxis2=dict(title='Harga Saham (Rp)', overlaying='y', side='right', showgrid=True),
            legend=dict(orientation="h", y=1.1, x=0)
        )
        st.plotly_chart(fig_cum, use_container_width=True)

# ==========================================
# --- TAB 3: WHALES IDENTITY TRACKING ---
# ==========================================
with tab3:
    st.subheader("Melacak Identitas Asli Pemegang Saham Kakap (>= 1%)")
    st.markdown("Di sini kita bisa melihat langsung *siapa nama entitas atau perusahaan konglomerasi asli* yang merubah kepemilikannya bulan ini.")
    
    if df_sn_ticker.empty:
        st.info("Data snapshot detil entitas tidak tersedia untuk saham ini.")
    else:
        unique_dates = sorted(df_sn_ticker['Date_norm'].unique())
        
        if len(unique_dates) < 2:
            st.warning("Dibutuhkan data minimal 2 bulan untuk melihat perubahan posisi Whales.")
            # Tetap tampilkan data bulan terakhir jika hanya ada 1 bulan
            latest_d = unique_dates[-1]
            st.dataframe(df_sn_ticker[df_sn_ticker['Date_norm'] == latest_d][['INVESTOR_NAME', 'INVESTOR_TYPE', 'PERCENTAGE']])
        else:
            # Bandingkan MoM Posisi Kepemilikan Whales
            t_curr = unique_dates[-1]
            t_prev = unique_dates[-2]
            
            df_c = df_sn_ticker[df_sn_ticker['Date_norm'] == t_curr][['INVESTOR_NAME', 'PERCENTAGE', 'INVESTOR_TYPE', 'DOMICILE']].rename(columns={'PERCENTAGE': 'Pct_Current'})
            df_p = df_sn_ticker[df_sn_ticker['Date_norm'] == t_prev][['INVESTOR_NAME', 'PERCENTAGE']].rename(columns={'PERCENTAGE': 'Pct_Previous'})
            
            # Gabungkan Data untuk melihat selisih perubahan persen kepemilikan saham individu kakap
            df_whale_change = pd.merge(df_c, df_p, on='INVESTOR_NAME', how='outer').fillna(0)
            df_whale_change['Perubahan Persentase MoM (%)'] = df_whale_change['Pct_Current'] - df_whale_change['Pct_Previous']
            
            # Saring entitas yang aktif bergerak melakukan transaksi perubahan porsi kepemilikan
            df_whale_active = df_whale_change[df_whale_change['Perubahan Persentase MoM (%)'] != 0].sort_values(by='Perubahan Persentase MoM (%)', ascending=False)
            
            st.markdown(f"### 🐋 Mutasi Transaksi Whales Terdeteksi (`{t_prev}` ➔ `{t_curr}`)")
            
            fig_change_whale = px.bar(
                df_whale_active,
                x='Perubahan Persentase MoM (%)',
                y='INVESTOR_NAME',
                orientation='h',
                color='Perubahan Persentase MoM (%)',
                color_continuous_scale=px.colors.diverging.Velocity,
                title="Aksi Transaksi Net Buy / Net Sell Pemegang Saham Kakap (>=1%)"
            )
            st.plotly_chart(fig_change_whale, use_container_width=True)
            
            st.markdown("#### Tabel Detil Mutasi Rekening Whales (>1%)")
            st.dataframe(
                df_whale_active[['INVESTOR_NAME', 'INVESTOR_TYPE', 'DOMICILE', 'Pct_Previous', 'Pct_Current', 'Perubahan Persentase MoM (%)']].reset_index(drop=True),
                use_container_width=True
            )
