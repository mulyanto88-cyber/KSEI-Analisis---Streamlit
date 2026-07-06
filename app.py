import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os

# Konfigurasi Utama Aplikasi
st.set_page_config(page_title="Smart Money & Bandarmologi Command Center", layout="wide")

st.title("🛰️ Smart Money & Bandarmologi Command Center")
st.markdown("Sistem Radar, Backtest Akumulasi, dan Pelacakan Entitas Whales Terpadu.")

# Sistem Caching Data Berkinerja Tinggi
@st.cache_data
def load_and_process_data(shareholder_file, snapshot_file):
    # 1. Proses Data Shareholder (Makro)
    df_sh = pd.read_csv(shareholder_file)
    df_sh['Date_parsed'] = pd.to_datetime(df_sh['Date'], format='%d/%m/%Y', errors='coerce')
    df_sh['Date_norm'] = df_sh['Date_parsed'].dt.strftime('%Y-%m-%d')
    
    # Kelompokkan Smart Money vs Retail
    funds_cols = ['Local_MF', 'Foreign_MF']
    corp_cols = ['Local_CP', 'Foreign_CP']
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

# Sidebar
st.sidebar.header("📁 Data Source Pipeline")
sh_default = "KSEI_Shareholder_Pure_KSEI_OK.csv"
sn_default = "KSE_1Persen_Monthly_Snapshot_OK.csv"

uploaded_sh = st.sidebar.file_uploader("Upload Shareholder CSV", type=["csv"])
uploaded_sn = st.sidebar.file_uploader("Upload 1% Snapshot CSV", type=["csv"])

file_sh_path = uploaded_sh if uploaded_sh is not None else (sh_default if os.path.exists(sh_default) else None)
file_sn_path = uploaded_sn if uploaded_sn is not None else (sn_default if os.path.exists(sn_default) else None)

if not file_sh_path or not file_sn_path:
    st.warning("⚠️ Menunggu pipeline data... Pastikan file CSV tersedia.")
    st.stop()

df_sh, df_sn = load_and_process_data(file_sh_path, file_sn_path)

# Filter Saham di Sidebar agar persisten antar tab
st.sidebar.markdown("---")
ticker_list = sorted(df_sh['Code'].unique())
selected_ticker = st.sidebar.selectbox("🎯 Ticker (Untuk Tab 2):", ticker_list, index=ticker_list.index('AADI') if 'AADI' in ticker_list else 0)

# =======================================================
# TAB UTAMA
# =======================================================
tab1, tab2 = st.tabs(["🛰️ Smart Money Radar & Validation", "🐳 Flow & Whales Tracker (Merged)"])

# ==========================================
# --- TAB 1: RADAR & VALIDASI 3 BULAN ---
# ==========================================
with tab1:
    st.subheader("Radar Akumulasi & Backtest Sinyal")
    st.markdown("Pantau saham potensial yang sedang diakumulasi, dan validasi pergerakan harga bulan depannya dari sinyal bulan-bulan sebelumnya.")
    
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        min_price = st.number_input("Harga Minimum (Rp)", min_value=0, value=100, step=50)
    with col_f2:
        smart_money_filter = st.selectbox("Sinyal Aliran Dana:", ["Active Funds & ETF Only", "Total Smart Money (Funds+Corp+Inst)"])
    with col_f3:
        retail_condition = st.checkbox("Hanya Tampilkan Saat Ritel Net SELL", value=True)
        
    # Ambil 3 bulan terakhir dari data (asumsi data berurutan: April, Mei, Juni)
    available_dates = sorted(df_sh['Date_norm'].unique())
    dates_to_show = available_dates[-3:] if len(available_dates) >= 3 else available_dates
    dates_to_show.reverse() # Urutkan dari yg terbaru (Juni, Mei, April)
    
    # Buat sub-tabs untuk masing-masing bulan
    month_tabs = st.tabs([f"Sinyal {d}" for d in dates_to_show])
    
    for i, target_date in enumerate(dates_to_show):
        with month_tabs[i]:
            df_curr = df_sh[df_sh['Date_norm'] == target_date].copy()
            df_curr = df_curr[df_curr['Price'] >= min_price]
            
            # Terapkan Filter
            if smart_money_filter == "Active Funds & ETF Only":
                df_curr['Net_Buy_Bandar'] = df_curr['Active_Funds_Net_Val']
            else:
                df_curr['Net_Buy_Bandar'] = df_curr['Smart_Money_Net_Val']
                
            if retail_condition:
                df_curr = df_curr[df_curr['Retail_Net_Val'] < 0]
            
            # Cari data bulan depannya untuk Backtest (Validasi Sinyal)
            date_idx = available_dates.index(target_date)
            has_next_month = date_idx + 1 < len(available_dates)
            
            if has_next_month:
                next_date = available_dates[date_idx + 1]
                df_next = df_sh[df_sh['Date_norm'] == next_date][['Code', 'Price']].rename(columns={'Price': 'Harga_Bulan_Depan'})
                df_curr = df_curr.merge(df_next, on='Code', how='left')
                df_curr['Validasi_Return_%'] = (df_curr['Harga_Bulan_Depan'] - df_curr['Price']) / df_curr['Price'] * 100
            else:
                df_curr['Harga_Bulan_Depan'] = np.nan
                df_curr['Validasi_Return_%'] = np.nan
            
            # Urutkan berdasarkan Net Buy Bandar
            df_curr = df_curr.sort_values(by='Net_Buy_Bandar', ascending=False).reset_index(drop=True)
            
            # Rename kolom untuk tampilan
            display_cols = ['Code', 'Price', 'Net_Buy_Bandar', 'Retail_Net_Val', 'Top_Buyer', 'Harga_Bulan_Depan', 'Validasi_Return_%']
            df_display = df_curr[display_cols].rename(columns={
                'Code': 'Ticker',
                'Price': 'Harga Sinyal',
                'Net_Buy_Bandar': 'Net Flow Bandar (IDR)',
                'Retail_Net_Val': 'Net Flow Ritel (IDR)',
                'Harga_Bulan_Depan': 'Harga Aktual Bulan Depan',
                'Validasi_Return_%': 'Kenaikan/Penurunan (%)'
            })
            
            st.markdown(f"**Saham dengan indikasi akumulasi pada {target_date}:**")
            
            if has_next_month:
                st.info(f"💡 Kolom **Kenaikan/Penurunan (%)** menunjukkan apakah sinyal pada {target_date} terbukti membuat harga naik di {next_date}.")
            else:
                st.warning(f"⚠️ Ini adalah bulan terakhir di data. Harga bulan depan belum tersedia untuk divalidasi.")
                
            st.dataframe(
                df_display.style.format({
                    'Net Flow Bandar (IDR)': '{:,.0f}',
                    'Net Flow Ritel (IDR)': '{:,.0f}',
                    'Harga Sinyal': 'Rp {:,}',
                    'Harga Aktual Bulan Depan': 'Rp {:,}',
                    'Kenaikan/Penurunan (%)': '{:+.2f}%'
                }).background_gradient(subset=['Kenaikan/Penurunan (%)'], cmap='RdYlGn'),
                use_container_width=True
            )

# ==========================================
# --- TAB 2: FLOW & WHALES TRACKER (MERGED) ---
# ==========================================
with tab2:
    st.subheader(f"Dashboard Analisis Mendalam: {selected_ticker}")
    
    df_sh_ticker = df_sh[df_sh['Code'] == selected_ticker].sort_values('Date_parsed').copy()
    df_sn_ticker = df_sn[df_sn['SHARE_CODE'] == selected_ticker].sort_values('DATE_parsed').copy()
    
    if df_sh_ticker.empty:
        st.error("Data tidak ditemukan.")
    else:
        # BAGIAN 1: STATUS & KUMULATIF FLOW
        latest = df_sh_ticker.iloc[-1]
        smart_flow = latest['Smart_Money_Net_Val']
        retail_flow = latest['Retail_Net_Val']
        
        st.markdown("### 🚦 Status Detektor Bandarmologi (Bulan Terakhir)")
        if smart_flow > 0 and retail_flow < 0:
            st.success("🔥 **AKUMULASI MASIF**: Big Money masuk secara agresif, Ritel sedang distribusi/cutloss.")
        elif smart_flow > 0 and retail_flow > 0:
            st.info("⚖️ **PARTISIPASI PUBLIK**: Big Money dan Ritel sama-sama masuk (Hati-hati, rawan guyuran).")
        elif smart_flow < 0 and retail_flow > 0:
            st.error("🚨 **DISTRIBUSI**: Big Money sedang jualan massal, Ritel yang menampung barang.")
        else:
            st.warning("📉 **MARK DOWN / SUNYA**: Kedua belah pihak cenderung pasif atau melakukan buangan kecil.")
            
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Active_Funds_Vol'], name='Vol Active Funds/ETF', line=dict(color='#00CC96', width=4)))
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Retail_Vol'], name='Vol Ritel (Individu)', line=dict(color='#EF553B', width=2, dash='dot')))
        fig_cum.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Price'], name='Harga Saham (Rp)', line=dict(color='#AB63FA', width=3), yaxis='y2'))
        fig_cum.update_layout(
            title="Tren Makro Kepemilikan Kategori vs Harga Saham",
            yaxis=dict(title='Lembar Saham', showgrid=False),
            yaxis2=dict(title='Harga (Rp)', overlaying='y', side='right', showgrid=True),
            legend=dict(orientation="h", y=1.1, x=0), height=400
        )
        st.plotly_chart(fig_cum, use_container_width=True)
        
        st.markdown("---")
        
        # BAGIAN 2: WHALES TRACKING (MOM & CORRELATION)
        st.markdown("### 🐋 Pelacakan Entitas Whales (>= 1%)")
        if df_sn_ticker.empty:
            st.info("Tidak ada entitas kakap >= 1% yang terdeteksi.")
        else:
            unique_dates = sorted(df_sn_ticker['Date_norm'].unique())
            
            # Peta Perubahan Mutasi Terakhir
            if len(unique_dates) >= 2:
                t_curr = unique_dates[-1]
                t_prev = unique_dates[-2]
                df_c = df_sn_ticker[df_sn_ticker['Date_norm'] == t_curr][['INVESTOR_NAME', 'PERCENTAGE', 'INVESTOR_TYPE']].rename(columns={'PERCENTAGE': 'Pct_Current'})
                df_p = df_sn_ticker[df_sn_ticker['Date_norm'] == t_prev][['INVESTOR_NAME', 'PERCENTAGE']].rename(columns={'PERCENTAGE': 'Pct_Previous'})
                
                df_whale_change = pd.merge(df_c, df_p, on='INVESTOR_NAME', how='outer').fillna(0)
                df_whale_change['Perubahan (%) MoM'] = df_whale_change['Pct_Current'] - df_whale_change['Pct_Previous']
                df_whale_active = df_whale_change[df_whale_change['Perubahan (%) MoM'] != 0].sort_values(by='Perubahan (%) MoM', ascending=False)
                
                col_w1, col_w2 = st.columns([1.5, 1])
                with col_w1:
                    if not df_whale_active.empty:
                        fig_change_whale = px.bar(
                            df_whale_active, x='Perubahan (%) MoM', y='INVESTOR_NAME', orientation='h',
                            color='Perubahan (%) MoM', color_continuous_scale=px.colors.diverging.RdYlGn,
                            title=f"Aksi Whales (Mutasi {t_prev} ➔ {t_curr})"
                        )
                        st.plotly_chart(fig_change_whale, use_container_width=True)
                    else:
                        st.write("Tidak ada perubahan kepemilikan Whales yang signifikan bulan ini.")
                with col_w2:
                    st.dataframe(df_whale_active[['INVESTOR_NAME', 'Perubahan (%) MoM']].set_index('INVESTOR_NAME'), use_container_width=True)
            
            st.markdown("#### 🔗 Korelasi Kepemilikan Entitas Spesifik vs Harga Saham")
            st.write("Validasi apakah lonjakan persentase kepemilikan (akumulasi) entitas tertentu memicu kenaikan harga saham.")
            
            whale_list = sorted(df_sn_ticker['INVESTOR_NAME'].unique())
            selected_whale = st.selectbox("Pilih Entitas Whale:", whale_list)
            
            # Ambil sejarah kepemilikan entitas ini
            df_whale_history = df_sn_ticker[df_sn_ticker['INVESTOR_NAME'] == selected_whale][['Date_norm', 'PERCENTAGE']]
            
            # Gabungkan dengan tabel harga saham
            df_corr = pd.merge(df_sh_ticker[['Date_norm', 'Price']], df_whale_history, on='Date_norm', how='left').fillna(0)
            
            # Hitung Korelasi Pearson jika data mencukupi
            if len(df_corr) > 1 and df_corr['PERCENTAGE'].std() != 0:
                corr_val = df_corr['Price'].corr(df_corr['PERCENTAGE'])
                st.metric("Koefisien Korelasi (Pearson)", f"{corr_val:+.2f}", 
                          "Korelasi Kuat (Menggerakkan Harga)" if abs(corr_val) >= 0.6 else "Korelasi Lemah")
            else:
                st.write("*Data entitas tidak bergerak atau periode terlalu singkat untuk menghitung korelasi.*")
            
            # Plot Korelasi
            fig_entity = go.Figure()
            fig_entity.add_trace(go.Bar(x=df_corr['Date_norm'], y=df_corr['PERCENTAGE'], name=f'Porsi {selected_whale} (%)', opacity=0.6, marker_color='#3498db'))
            fig_entity.add_trace(go.Scatter(x=df_corr['Date_norm'], y=df_corr['Price'], name='Harga Saham (Rp)', mode='lines+markers', line=dict(color='#e74c3c', width=3), yaxis='y2'))
            
            fig_entity.update_layout(
                title=f"Pergerakan Kepemilikan {selected_whale} Terhadap Harga {selected_ticker}",
                yaxis=dict(title='Persentase Kepemilikan (%)', showgrid=False),
                yaxis2=dict(title='Harga Saham (Rp)', overlaying='y', side='right', showgrid=True),
                legend=dict(orientation="h", y=1.1, x=0), height=400
            )
            st.plotly_chart(fig_entity, use_container_width=True)
