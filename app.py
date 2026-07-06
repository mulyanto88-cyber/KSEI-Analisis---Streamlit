import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# Set Konfigurasi Halaman
st.set_page_config(page_title="KSEI Shareholder & 1% Snapshot Analytics", layout="wide")

st.title("📊 KSEI Shareholder & 1% Snapshot Analytics Dashboard")
st.markdown("Dashboard ini digunakan untuk menganalisis korelasi struktur kepemilikan investor terhadap pergerakan harga saham.")

# Fungsi untuk memuat data
@st.cache_data
def load_data(shareholder_file, snapshot_file):
    # Load Shareholder Data
    df_sh = pd.read_csv(shareholder_file)
    df_sh['Date_parsed'] = pd.to_datetime(df_sh['Date'], format='%d/%m/%Y', errors='coerce')
    df_sh['Date_norm'] = df_sh['Date_parsed'].dt.strftime('%Y-%m-%d')
    
    # Load Snapshot Data
    df_sn = pd.read_csv(snapshot_file)
    df_sn['DATE_parsed'] = pd.to_datetime(df_sn['DATE'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_sn['Date_norm'] = df_sn['DATE_parsed'].dt.strftime('%Y-%m-%d')
    
    return df_sh, df_sn

# Sidebar - Upload atau Deteksi Otomatis File
st.sidebar.header("📁 Data Source")
sh_default = "KSEI_Shareholder_Pure_KSEI_OK.csv"
sn_default = "KSE_1Persen_Monthly_Snapshot_OK.csv"

uploaded_sh = st.sidebar.file_uploader("Upload Shareholder Pure KSEI CSV", type=["csv"])
uploaded_sn = st.sidebar.file_uploader("Upload 1% Monthly Snapshot CSV", type=["csv"])

# Tentukan file mana yang dipakai
file_sh_path = uploaded_sh if uploaded_sh is not None else (sh_default if os.path.exists(sh_default) else None)
file_sn_path = uploaded_sn if uploaded_sn is not None else (sn_default if os.path.exists(sn_default) else None)

if not file_sh_path or not file_sn_path:
    st.warning("⚠️ Silakan upload kedua file CSV di sidebar atau pastikan file berada di direktori yang sama dengan nama default.")
    st.stop()

# Load data ke DataFrame
df_sh, df_sn = load_data(file_sh_path, file_sn_path)
st.success("✅ Data berhasil dimuat!")

# Kategori Singkatan Investor KSEI
ksei_labels = {
    'IS': 'Insurance (Asuransi)',
    'CP': 'Corporate (Perusahaan)',
    'PF': 'Pension Fund (Dana Pensiun)',
    'IB': 'Investment Bank',
    'ID': 'Individual (Ritel)',
    'MF': 'Mutual Fund (Reksa Dana)',
    'SC': 'Securities Company (Sekuritas)',
    'FD': 'Foundation (Yayasan)',
    'OT': 'Others (Lain-lain)'
}

# Sidebar - Filter Saham
ticker_list = sorted(df_sh['Code'].unique())
selected_ticker = st.sidebar.selectbox("🎯 Pilih Kode Saham (Ticker):", ticker_list, index=ticker_list.index('AADI') if 'AADI' in ticker_list else 0)

# Filter Data Berdasarkan Ticker
df_sh_ticker = df_sh[df_sh['Code'] == selected_ticker].sort_values('Date_parsed')
df_sn_ticker = df_sn[df_sn['SHARE_CODE'] == selected_ticker].sort_values('DATE_parsed')

# Tab Layout untuk Analisis
tab1, tab2, tab3 = st.tabs(["📈 Analisis Pergerakan Harga & Kategori", "👥 Analisis Investor Besar (>1%)", "🔍 Korelasi Detail"])

# --- TAB 1: PERGERAKAN HARGA & KATEGORI ---
with tab1:
    st.subheader(f"Analisis Struktur Kepemilikan & Harga Saham: {selected_ticker}")
    
    if df_sh_ticker.empty:
        st.write("Data tidak ditemukan untuk ticker ini.")
    else:
        # Metrik Ringkasan Utama
        latest_row = df_sh_ticker.iloc[-1]
        m1, m2, m3 = st.columns(3)
        m1.metric("Harga Terakhir", f"Rp {latest_row['Price']:,}")
        m2.metric("Total Kepemilikan Lokal", f"{latest_row['Total_Local']:,.0f} Lembar")
        m3.metric("Total Kepemilikan Asing", f"{latest_row['Total_Foreign']:,.0f} Lembar")
        
        # Grafik 1: Harga vs Komposisi Asing vs Lokal
        fig_price_comp = go.Figure()
        fig_price_comp.add_trace(go.Bar(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Total_Local'], name='Total Local Shares', yaxis='y'))
        fig_price_comp.add_trace(go.Bar(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Total_Foreign'], name='Total Foreign Shares', yaxis='y'))
        fig_price_comp.add_trace(go.Scatter(x=df_sh_ticker['Date_norm'], y=df_sh_ticker['Price'], name='Stock Price', mode='lines+markers', line=dict(color='black', width=3), yaxis='y2'))
        
        fig_price_comp.update_layout(
            title=f"Tren Harga vs Porsi Kepemilikan Lokal/Asing - {selected_ticker}",
            barmode='stack',
            xaxis=dict(title='Tanggal'),
            yaxis=dict(title='Volume Saham (Lembar)', showgrid=False),
            yaxis2=dict(title='Harga Saham (Rp)', overlaying='y', side='right', showgrid=True),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_price_comp, use_container_width=True)
        
        # Grafik 2: Breakdown Kategori Investor Lokal & Asing (Latest Date)
        st.markdown("### Komposisi Detail Kategori Investor Terakhir")
        c1, c2 = st.columns(2)
        
        local_cols = [f'Local_{k}' for k in ksei_labels.keys()]
        foreign_cols = [f'Foreign_{k}' for k in ksei_labels.keys()]
        
        df_local_pie = pd.DataFrame({
            'Kategori': [ksei_labels[k.split('_')[1]] for k in local_cols],
            'Volume': latest_row[local_cols].values
        })
        df_foreign_pie = pd.DataFrame({
            'Kategori': [ksei_labels[k.split('_')[1]] for k in foreign_cols],
            'Volume': latest_row[foreign_cols].values
        })
        
        with c1:
            fig_local = px.pie(df_local_pie, values='Volume', names='Kategori', title="Proporsi Investor Lokal (Terakhir)", hole=0.3)
            st.plotly_chart(fig_local, use_container_width=True)
        with c2:
            fig_foreign = px.pie(df_foreign_pie, values='Volume', names='Kategori', title="Proporsi Investor Asing (Terakhir)", hole=0.3)
            st.plotly_chart(fig_foreign, use_container_width=True)

# --- TAB 2: INVESTOR BESAR (>1%) ---
with tab2:
    st.subheader(f"Profil Pemegang Saham Kakap (>= 1%): {selected_ticker}")
    
    if df_sn_ticker.empty:
        st.info("Tidak ada data snapshot pemegang saham >= 1% untuk ticker ini.")
    else:
        # Pilihan tanggal snapshot yang tersedia
        available_dates = sorted(df_sn_ticker['Date_norm'].unique())
        selected_date = st.selectbox("📅 Pilih Tanggal Snapshot:", available_dates, index=len(available_dates)-1)
        
        df_sn_date = df_sn_ticker[df_sn_ticker['Date_norm'] == selected_date].sort_values('PERCENTAGE', ascending=False)
        
        # Konsentrasi Kepemilikan Top Holder
        total_top_pct = df_sn_date['PERCENTAGE'].sum()
        st.metric("Total Konsentrasi Kepemilikan Top Holders (>1%)", f"{total_top_pct:.2f} %")
        
        # Bar Chart Pemegang Saham Terbesar
        fig_top_holders = px.bar(
            df_sn_date.head(15), 
            x='PERCENTAGE', 
            y='INVESTOR_NAME', 
            orientation='h',
            title=f"15 Pemegang Saham Terbesar pada {selected_date}",
            labels={'PERCENTAGE': 'Persentase Kepemilikan (%)', 'INVESTOR_NAME': 'Nama Investor'},
            color='LOCAL_FOREIGN',
            color_discrete_map={'L': '#636EFA', 'F': '#EF553B'}
        )
        fig_top_holders.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top_holders, use_container_width=True)
        
        # Tabel Data Lengkap Pemegang Saham >= 1%
        st.markdown("#### Tabel Lengkap Pemegang Saham >= 1%")
        st.dataframe(df_sn_date[['INVESTOR_NAME', 'INVESTOR_TYPE', 'LOCAL_FOREIGN', 'DOMICILE', 'TOTAL_HOLDING_SHARES', 'PERCENTAGE']].reset_index(drop=True), use_container_width=True)

# --- TAB 3: KORELASI DETAIL ---
with tab3:
    st.subheader(f"Analisis Korelasi Perubahan Volume Kategori Investor vs Return Harga")
    
    if not df_sh_ticker.empty and len(df_sh_ticker) > 1:
        # Hitung persentase perubahan harga bulanan
        df_sh_ticker['Price_Return_Pct'] = df_sh_ticker['Price'].pct_change() * 100
        
        # Cari semua kolom perubahan volume (_Chg_Vol)
        chg_cols = [c for c in df_sh_ticker.columns if c.endswith('_Chg_Vol')]
        
        # Korelasi antara perubahan volume dan return harga untuk saham pilihan
        corr_data = df_sh_ticker[chg_cols + ['Price_Return_Pct']].corr()['Price_Return_Pct'].drop('Price_Return_Pct').reset_index()
        corr_data.columns = ['Kategori KSEI', 'Koefisien Korelasi dengan Return Harga']
        corr_data = corr_data.sort_values('Koefisien Korelasi dengan Return Harga', ascending=False)
        
        # Bersihkan nama kategori agar mudah dibaca
        def clean_name(col):
            parts = col.split('_')
            return f"{'Lokal' if parts[0]=='Local' else 'Asing'} - {ksei_labels.get(parts[1], parts[1])}"
        
        corr_data['Nama Kategori'] = corr_data['Kategori KSEI'].apply(clean_name)
        
        st.markdown("Korelasi positif yang tinggi menunjukkan bahwa saat kategori investor tersebut banyak membeli/akumulasi saham ini, harga saham cenderung naik.")
        
        # Plot Korelasi
        fig_corr = px.bar(
            corr_data, 
            x='Koefisien Korelasi dengan Return Harga', 
            y='Nama Kategori', 
            orientation='h',
            title=f"Korelasi Perubahan Volume Investor vs Return Harga Bulanan ({selected_ticker})",
            color='Koefisien Korelasi dengan Return Harga',
            color_continuous_scale=px.colors.diverging.RdBu
        )
        fig_corr.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_corr, use_container_width=True)
        
        # Scatter Plot Exploratory
        st.markdown("### 👀 Deteksi Gerakan (Scatter Plot Finder)")
        selected_chg_col = st.selectbox("Pilih Kategori Investor untuk dilihat sebaran hubungannya dengan harga:", corr_data['Kategori KSEI'].tolist())
        
        fig_scatter = px.scatter(
            df_sh_ticker.dropna(subset=['Price_Return_Pct']),
            x=selected_chg_col,
            y='Price_Return_Pct',
            text='Date_norm',
            labels={selected_chg_col: 'Perubahan Volume (Lembar)', 'Price_Return_Pct': 'Return Harga (%)'},
            title=f"Hubungan Perubahan Volume {clean_name(selected_chg_col)} vs Return Harga Bulanan",
            trendline="ols" if len(df_sh_ticker.dropna(subset=['Price_Return_Pct'])) > 2 else None
        )
        fig_scatter.update_traces(textposition='top center', marker=dict(size=12, color='#00CC96'))
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Dibutuhkan data historis lebih dari 1 bulan untuk menghitung korelasi return harga.")
