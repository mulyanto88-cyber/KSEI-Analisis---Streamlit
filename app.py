import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
import io

st.set_page_config(page_title="Smart Money & Bandarmologi Command Center", layout="wide")
st.title("🛰️ Smart Money & Bandarmologi Command Center")
st.markdown("Sistem Radar, Backtest Akumulasi, dan Pelacakan Entitas Whales Terpadu.")

# =========================================================
# DATA LOADING
# =========================================================
def identify_files(uploaded_files):
    sh = sn = None
    for f in uploaded_files:
        name_lower = f.name.lower()
        if 'shareholder' in name_lower or 'pure_ksei' in name_lower:
            sh = f
        elif 'snapshot' in name_lower or '1persen' in name_lower or '1_persen' in name_lower:
            sn = f
    return sh, sn

st.sidebar.header("📁 Data Source Pipeline")
uploaded_files = st.sidebar.file_uploader(
    "Upload 2 File CSV (Shareholder + Snapshot 1%)",
    type=["csv"],
    accept_multiple_files=True,
    help="Pilih kedua file CSV sekaligus. Nama file harus mengandung 'shareholder' dan 'snapshot'."
)

if uploaded_files and len(uploaded_files) >= 2:
    sh_file, sn_file = identify_files(uploaded_files)
    if sh_file is None or sn_file is None:
        st.sidebar.error("❌ Tidak dapat mengidentifikasi file. Pastikan satu file mengandung 'shareholder' dan satu lagi 'snapshot'/'1persen'.")
        st.stop()
    st.sidebar.success(f"✅ Shareholder: {sh_file.name}\n✅ Snapshot: {sn_file.name}")
    file_sh_path = sh_file
    file_sn_path = sn_file
else:
    sh_default = os.path.join(os.path.dirname(__file__), "..", "KSEI_Shareholder_Pure_KSEI_OK.csv")
    sn_default = os.path.join(os.path.dirname(__file__), "..", "KSE_1Persen_Monthly_Snapshot_OK.csv")
    alt_sh = "KSEI_Shareholder_Pure_KSEI_OK.csv"
    alt_sn = "KSE_1Persen_Monthly_Snapshot_OK.csv"
    if os.path.exists(sh_default):
        file_sh_path = sh_default
        file_sn_path = sn_default if os.path.exists(sn_default) else (alt_sn if os.path.exists(alt_sn) else None)
    elif os.path.exists(alt_sh):
        file_sh_path = alt_sh
        file_sn_path = alt_sn if os.path.exists(alt_sn) else None
    else:
        file_sh_path = file_sn_path = None

if not file_sh_path or not file_sn_path:
    st.warning("⚠️ Menunggu pipeline data... Upload 2 file CSV di sidebar atau pastikan file default tersedia.")
    st.stop()

@st.cache_data
def load_and_process_data(shareholder_file, snapshot_file):
    df_sh = pd.read_csv(shareholder_file)
    df_sh['Date_parsed'] = pd.to_datetime(df_sh['Date'], format='%d/%m/%Y', errors='coerce')
    df_sh['Date_norm'] = df_sh['Date_parsed'].dt.strftime('%Y-%m-%d')

    funds_cols = ['Local_MF', 'Foreign_MF']
    corp_cols = ['Local_CP', 'Foreign_CP']
    inst_cols = ['Local_IS', 'Local_PF', 'Local_IB', 'Local_SC', 'Foreign_IS', 'Foreign_PF', 'Foreign_IB', 'Foreign_SC']

    df_sh['Smart_Money_Vol'] = df_sh[funds_cols + corp_cols + inst_cols].sum(axis=1)
    df_sh['Active_Funds_Vol'] = df_sh[funds_cols].sum(axis=1)
    df_sh['Corporate_Vol'] = df_sh[corp_cols].sum(axis=1)
    df_sh['Retail_Vol'] = df_sh['Local_ID'] + df_sh['Foreign_ID']

    df_sh['Smart_Money_Net_Val'] = df_sh[['Local_MF_Chg_Val','Foreign_MF_Chg_Val','Local_CP_Chg_Val','Foreign_CP_Chg_Val',
                                           'Local_IS_Chg_Val','Local_PF_Chg_Val','Local_IB_Chg_Val','Local_SC_Chg_Val',
                                           'Foreign_IS_Chg_Val','Foreign_PF_Chg_Val','Foreign_IB_Chg_Val','Foreign_SC_Chg_Val']].sum(axis=1)
    df_sh['Active_Funds_Net_Val'] = df_sh[['Local_MF_Chg_Val','Foreign_MF_Chg_Val']].sum(axis=1)
    df_sh['Retail_Net_Val'] = df_sh['Local_ID_Chg_Val'] + df_sh['Foreign_ID_Chg_Val']
    df_sh['Corporate_Net_Val'] = df_sh[['Local_CP_Chg_Val','Foreign_CP_Chg_Val']].sum(axis=1)

    df_sn = pd.read_csv(snapshot_file)
    df_sn['DATE_parsed'] = pd.to_datetime(df_sn['DATE'], format='%d/%m/%Y %H:%M', errors='coerce')
    df_sn['Date_norm'] = df_sn['DATE_parsed'].dt.strftime('%Y-%m-%d')

    return df_sh, df_sn

df_sh, df_sn = load_and_process_data(file_sh_path, file_sn_path)

available_dates = sorted(df_sh['Date_norm'].unique())

# =========================================================
# SIDEBAR FILTERS
# =========================================================
st.sidebar.markdown("---")
st.sidebar.header("🎛️ Filter Global")

# Date range selector
date_start, date_end = st.sidebar.select_slider(
    "Rentang Waktu",
    options=available_dates,
    value=(available_dates[0], available_dates[-1])
)
filtered_dates = [d for d in available_dates if date_start <= d <= date_end]

ticker_list = sorted(df_sh['Code'].unique())
selected_ticker = st.sidebar.selectbox("🎯 Ticker (Tab 2 & 3):", ticker_list, index=ticker_list.index('AADI') if 'AADI' in ticker_list else 0)

# Price range slider
price_min_global = int(df_sh['Price'].min())
price_max_global = int(df_sh['Price'].max())
price_range = st.sidebar.slider("Rentang Harga (Rp)", min_value=price_min_global, max_value=price_max_global, value=(price_min_global, price_max_global))

# =========================================================
# SMART MONEY SCORE ENGINE
# =========================================================
def compute_smart_money_score(df_subset):
    scores = []
    for code, grp in df_subset.groupby('Code'):
        grp = grp.sort_values('Date_norm')
        score = 0
        sm_net = grp['Smart_Money_Net_Val'].sum()
        rt_net = grp['Retail_Net_Val'].sum()
        cp_net = grp['Corporate_Net_Val'].sum()

        if sm_net > 0 and rt_net < 0:
            score += 40
        elif sm_net > 0:
            score += 20
        if cp_net > 0:
            score += 15
        if len(grp) >= 2:
            sm_trend = grp['Smart_Money_Net_Val'].iloc[-1] - grp['Smart_Money_Net_Val'].iloc[0]
            if sm_trend > 0:
                score += 20
            if (grp['Smart_Money_Net_Val'] > 0).sum() >= 2:
                score += 15
        if rt_net < 0:
            score += 10

        latest_price = grp['Price'].iloc[-1]
        scores.append({'Code': code, 'Smart_Money_Score': score, 'Latest_Price': latest_price,
                       'Total_SM_Net_Val': sm_net, 'Total_Retail_Net_Val': rt_net,
                       'Num_Months': len(grp), 'Type': grp['Type'].iloc[0] if 'Type' in grp.columns else ''})
    return pd.DataFrame(scores).sort_values('Smart_Money_Score', ascending=False)

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "🛰️ Smart Money Radar",
    "📊 Top Movers & Sektor",
    "🐋 Flow & Whales Tracker",
    "🔔 Alert & Export"
])

# =========================================================
# TAB 1: RADAR
# =========================================================
with tab1:
    st.subheader("Radar Akumulasi & Backtest Sinyal")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    with col_f1:
        smart_money_filter = st.selectbox("Sinyal Aliran Dana:", ["Active Funds & ETF Only", "Total Smart Money (Funds+Corp+Inst)"], key="tab1_sm")
    with col_f2:
        retail_condition = st.checkbox("Hanya Saat Ritel Net SELL", value=True, key="tab1_retail")
    with col_f3:
        min_net_flow = st.number_input("Min Net Flow Bandar (Rp)", min_value=0, value=0, step=100_000_000, format="%d")
    with col_f4:
        top_n = st.number_input("Top N Saham", min_value=5, max_value=200, value=50, step=5)

    dates_to_show = filtered_dates[-3:] if len(filtered_dates) >= 3 else filtered_dates
    dates_to_show.reverse()
    month_tabs = st.tabs([f"Sinyal {d}" for d in dates_to_show])

    for i, target_date in enumerate(dates_to_show):
        with month_tabs[i]:
            df_curr = df_sh[(df_sh['Date_norm'] == target_date) & (df_sh['Price'].between(price_range[0], price_range[1]))].copy()

            if smart_money_filter == "Active Funds & ETF Only":
                df_curr['Net_Buy_Bandar'] = df_curr['Active_Funds_Net_Val']
            else:
                df_curr['Net_Buy_Bandar'] = df_curr['Smart_Money_Net_Val']
            if retail_condition:
                df_curr = df_curr[df_curr['Retail_Net_Val'] < 0]
            df_curr = df_curr[df_curr['Net_Buy_Bandar'] >= min_net_flow]

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

            df_curr = df_curr.sort_values('Net_Buy_Bandar', ascending=False).head(top_n).reset_index(drop=True)

            display_cols = ['Code', 'Price', 'Net_Buy_Bandar', 'Retail_Net_Val', 'Top_Buyer', 'Harga_Bulan_Depan', 'Validasi_Return_%']
            df_display = df_curr[display_cols].rename(columns={
                'Code': 'Ticker', 'Price': 'Harga Sinyal', 'Net_Buy_Bandar': 'Net Flow Bandar (IDR)',
                'Retail_Net_Val': 'Net Flow Ritel (IDR)', 'Harga_Bulan_Depan': 'Harga Aktual Bulan Depan',
                'Validasi_Return_%': 'Kenaikan/Penurunan (%)'
            })

            st.markdown(f"**Saham dengan indikasi akumulasi pada {target_date}:**")
            if has_next_month:
                st.info(f"💡 Kolom **Kenaikan/Penurunan (%)** memvalidasi sinyal {target_date} di {next_date}.")
            else:
                st.warning("⚠️ Bulan terakhir — validasi belum tersedia.")

            styled_df = df_display.style.format({
                'Net Flow Bandar (IDR)': '{:,.0f}', 'Net Flow Ritel (IDR)': '{:,.0f}',
                'Harga Sinyal': 'Rp {:,}', 'Harga Aktual Bulan Depan': 'Rp {:,}',
                'Kenaikan/Penurunan (%)': '{:+.2f}%'
            })
            if has_next_month:
                styled_df = styled_df.background_gradient(subset=['Kenaikan/Penurunan (%)'], cmap='RdYlGn')

            st.dataframe(styled_df, use_container_width=True)

            # Mini chart: Top 10 bar
            top10 = df_curr.head(10).copy()
            if not top10.empty:
                fig_top = px.bar(top10, x='Code', y='Net_Buy_Bandar', color='Validasi_Return_%' if has_next_month else None,
                                 color_continuous_scale='RdYlGn', title=f"Top 10 Net Flow Bandar - {target_date}")
                st.plotly_chart(fig_top, use_container_width=True)

# =========================================================
# TAB 2: TOP MOVERS & SEKTOR
# =========================================================
with tab2:
    st.subheader("Top Movers & Sektor Aggregation")

    tab2a, tab2b = st.tabs(["📈 Top Movers Keseluruhan", "🏭 Analisa Sektor"])

    with tab2a:
        st.markdown("### Top Movers — Net Flow Bandar Terbesar")
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            top_m_n = st.number_input("Jumlah Top Movers", min_value=5, max_value=100, value=30, step=5, key="topm_n")
        with col_m2:
            top_m_date = st.selectbox("Bulan Analisa", filtered_dates, index=len(filtered_dates)-1, key="topm_date")

        df_tm = df_sh[(df_sh['Date_norm'] == top_m_date) & (df_sh['Price'].between(price_range[0], price_range[1]))].copy()
        df_tm['SM_Net'] = df_tm['Smart_Money_Net_Val']
        df_tm['Retail_Net'] = df_tm['Retail_Net_Val']

        top_sm = df_tm.nlargest(top_m_n, 'SM_Net')[['Code', 'Price', 'SM_Net', 'Retail_Net', 'Type', 'Top_Buyer']].reset_index(drop=True)
        top_retail_sell = df_tm.nsmallest(top_m_n, 'Retail_Net')[['Code', 'Price', 'SM_Net', 'Retail_Net', 'Type']].reset_index(drop=True)

        col_top1, col_top2 = st.columns(2)
        with col_top1:
            st.markdown("#### 🔥 Top Smart Money Net Buy")
            st.dataframe(top_sm.style.format({'SM_Net': '{:,.0f}', 'Retail_Net': '{:,.0f}', 'Price': 'Rp {:,}'}), use_container_width=True)
        with col_top2:
            st.markdown("#### 🔴 Top Retail Net Sell (Distribusi Ritel)")
            st.dataframe(top_retail_sell.style.format({'SM_Net': '{:,.0f}', 'Retail_Net': '{:,.0f}', 'Price': 'Rp {:,}'}), use_container_width=True)

        # Area chart tren
        st.markdown("### Tren Akumulasi — Top 5 Ticker Terpilih")
        top5_codes = top_sm.head(5)['Code'].tolist()
        df_trend = df_sh[df_sh['Code'].isin(top5_codes) & df_sh['Date_norm'].isin(filtered_dates)]
        if not df_trend.empty:
            fig_trend = px.area(df_trend, x='Date_norm', y='Smart_Money_Net_Val', color='Code',
                                title='Tren Smart Money Net Flow — Top 5 (per Bulan)', markers=True)
            st.plotly_chart(fig_trend, use_container_width=True)

    with tab2b:
        st.markdown("### Aggregasi Sektor / Tipe")
        agg_col1, agg_col2 = st.columns(2)
        with agg_col1:
            agg_date = st.selectbox("Bulan", filtered_dates, index=len(filtered_dates)-1, key="agg_date")
        with agg_col2:
            agg_metric = st.selectbox("Metrik", ["Smart_Money_Net_Val", "Active_Funds_Net_Val", "Retail_Net_Val", "Smart_Money_Vol"], key="agg_metric")

        df_agg = df_sh[(df_sh['Date_norm'] == agg_date) & (df_sh['Price'].between(price_range[0], price_range[1]))]
        sector_agg = df_agg.groupby('Type').agg(
            Total_Flow=(agg_metric, 'sum'),
            Avg_Price=('Price', 'mean'),
            Ticker_Count=('Code', 'nunique'),
            Top_Ticker=('Code', lambda x: x.iloc[0])
        ).sort_values('Total_Flow', ascending=False).reset_index()

        if not sector_agg.empty:
            col_s1, col_s2 = st.columns([1.5, 1])
            with col_s1:
                fig_sector = px.bar(sector_agg, x='Type', y='Total_Flow', color='Total_Flow',
                                    color_continuous_scale='Viridis', title=f"{agg_metric} per Sektor - {agg_date}",
                                    hover_data={'Ticker_Count': True, 'Avg_Price': ':.0f'})
                st.plotly_chart(fig_sector, use_container_width=True)
            with col_s2:
                st.dataframe(sector_agg.style.format({'Total_Flow': '{:,.0f}', 'Avg_Price': 'Rp {:,}'}), use_container_width=True)

            # Treemap
            fig_tree = px.treemap(sector_agg, path=['Type'], values='Total_Flow', title='Treemap Aliran Dana per Sektor',
                                  color='Total_Flow', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_tree, use_container_width=True)

# =========================================================
# TAB 3: FLOW & WHALES
# =========================================================
with tab3:
    st.subheader(f"Dashboard Analisis Mendalam: {selected_ticker}")

    compare_mode = st.checkbox("Mode Bandingkan 2 Ticker", key="compare_mode")
    if compare_mode:
        ticker2 = st.selectbox("Ticker Pembanding", [t for t in ticker_list if t != selected_ticker], key="ticker2")
    else:
        ticker2 = None

    def render_ticker_dashboard(ticker, label="", cols=None):
        df_sh_t = df_sh[df_sh['Code'] == ticker].sort_values('Date_parsed').copy()
        df_sn_t = df_sn[df_sn['SHARE_CODE'] == ticker].sort_values('DATE_parsed').copy()

        if df_sh_t.empty:
            if cols: cols[0].error(f"Data tidak ditemukan untuk {ticker}")
            else: st.error(f"Data tidak ditemukan untuk {ticker}")
            return

        latest = df_sh_t.iloc[-1]
        smart_flow = latest['Smart_Money_Net_Val']
        retail_flow = latest['Retail_Net_Val']

        target_col = cols[0] if cols else st
        target_col.markdown(f"### {label}Status Detektor: {ticker}")
        if smart_flow > 0 and retail_flow < 0:
            target_col.success("🔥 **AKUMULASI MASIF**: Big Money masuk agresif, Ritel distribusi.")
        elif smart_flow > 0 and retail_flow > 0:
            target_col.info("⚖️ **PARTISIPASI PUBLIK**: Keduanya masuk (hati-hati guyuran).")
        elif smart_flow < 0 and retail_flow > 0:
            target_col.error("🚨 **DISTRIBUSI**: Big Money jualan massal, Ritel menampung.")
        else:
            target_col.warning("📉 **MARK DOWN**: Kedua pihak pasif.")

        # Multi-axis chart: Volume & Harga
        fig_cum = go.Figure()
        fig_cum.add_trace(go.Scatter(x=df_sh_t['Date_norm'], y=df_sh_t['Active_Funds_Vol'], name='Vol Active Funds', line=dict(color='#00CC96', width=4)))
        fig_cum.add_trace(go.Scatter(x=df_sh_t['Date_norm'], y=df_sh_t['Retail_Vol'], name='Vol Ritel', line=dict(color='#EF553B', width=2, dash='dot')))
        fig_cum.add_trace(go.Scatter(x=df_sh_t['Date_norm'], y=df_sh_t['Smart_Money_Net_Val'], name='SM Net Flow (IDR)', line=dict(color='#FFA15A', width=2), yaxis='y3'))
        fig_cum.add_trace(go.Scatter(x=df_sh_t['Date_norm'], y=df_sh_t['Price'], name='Harga (Rp)', line=dict(color='#AB63FA', width=3), yaxis='y2'))
        fig_cum.update_layout(
            title=f"Tren Lengkap {ticker}",
            yaxis=dict(title='Volume (Lembar)', showgrid=False),
            yaxis2=dict(title='Harga (Rp)', overlaying='y', side='right', showgrid=True),
            yaxis3=dict(title='Net Flow (IDR)', overlaying='y', side='left', position=0.05, showgrid=False),
            legend=dict(orientation="h", y=1.1, x=0), height=400
        )
        target_col.plotly_chart(fig_cum, use_container_width=True)

        # Whales
        target_col.markdown("### 🐋 Pelacakan Entitas Whales (>= 1%)")
        if df_sn_t.empty:
            target_col.info("Tidak ada entitas kakap >= 1%.")
            return

        unique_dates = sorted(df_sn_t['Date_norm'].unique())
        if len(unique_dates) >= 2:
            t_curr = unique_dates[-1]
            t_prev = unique_dates[-2]
            df_c = df_sn_t[df_sn_t['Date_norm'] == t_curr][['INVESTOR_NAME', 'PERCENTAGE', 'INVESTOR_TYPE']].rename(columns={'PERCENTAGE': 'Pct_Current'})
            df_p = df_sn_t[df_sn_t['Date_norm'] == t_prev][['INVESTOR_NAME', 'PERCENTAGE']].rename(columns={'PERCENTAGE': 'Pct_Previous'})
            df_whale_change = pd.merge(df_c, df_p, on='INVESTOR_NAME', how='outer').fillna(0)
            df_whale_change['Perubahan (%) MoM'] = df_whale_change['Pct_Current'] - df_whale_change['Pct_Previous']
            df_whale_active = df_whale_change[df_whale_change['Perubahan (%) MoM'] != 0].sort_values('Perubahan (%) MoM', ascending=False)

            col_w1, col_w2 = st.columns([1.5, 1])
            with col_w1:
                if not df_whale_active.empty:
                    fig_whale = px.bar(df_whale_active, x='Perubahan (%) MoM', y='INVESTOR_NAME', orientation='h',
                                       color='Perubahan (%) MoM', color_continuous_scale='RdYlGn',
                                       title=f"Aksi Whales {t_prev} → {t_curr}")
                    st.plotly_chart(fig_whale, use_container_width=True)
            with col_w2:
                st.dataframe(df_whale_active[['INVESTOR_NAME', 'Perubahan (%) MoM']].set_index('INVESTOR_NAME'), use_container_width=True)

        # Whales Concentration Index
        if unique_dates:
            latest_date = unique_dates[-1]
            df_latest_whale = df_sn_t[df_sn_t['Date_norm'] == latest_date]
            top5_pct = df_latest_whale.nlargest(5, 'PERCENTAGE')['PERCENTAGE'].sum()
            wci = min(top5_pct / 100.0, 1.0)
            st.metric("🐋 Whales Concentration Index (Top 5)", f"{top5_pct:.1f}%",
                      "Terkonsentrasi" if wci >= 0.5 else "Tersebar", delta_color="inverse")

        # Entity correlation
        whale_list = sorted(df_sn_t['INVESTOR_NAME'].unique())
        selected_whale = st.selectbox(f"Pilih Entitas Whale - {ticker}", whale_list, key=f"whale_{ticker}")

        df_whale_history = df_sn_t[df_sn_t['INVESTOR_NAME'] == selected_whale][['Date_norm', 'PERCENTAGE']]
        df_corr = pd.merge(df_sh_t[['Date_norm', 'Price']], df_whale_history, on='Date_norm', how='left').fillna(0)

        if len(df_corr) > 1 and df_corr['PERCENTAGE'].std() != 0:
            corr_val = df_corr['Price'].corr(df_corr['PERCENTAGE'])
            st.metric(f"Korelasi {selected_whale} vs Harga", f"{corr_val:+.2f}",
                      "Kuat" if abs(corr_val) >= 0.6 else "Lemah")
        else:
            st.write("*Data tidak bergerak atau terlalu singkat.*")

        fig_entity = go.Figure()
        fig_entity.add_trace(go.Bar(x=df_corr['Date_norm'], y=df_corr['PERCENTAGE'], name=f'Porsi {selected_whale} (%)', opacity=0.6, marker_color='#3498db'))
        fig_entity.add_trace(go.Scatter(x=df_corr['Date_norm'], y=df_corr['Price'], name='Harga (Rp)', mode='lines+markers', line=dict(color='#e74c3c', width=3), yaxis='y2'))
        fig_entity.update_layout(
            title=f"{selected_whale} vs Harga {ticker}",
            yaxis=dict(title='%', showgrid=False),
            yaxis2=dict(title='Harga (Rp)', overlaying='y', side='right', showgrid=True),
            legend=dict(orientation="h", y=1.1, x=0), height=400
        )
        st.plotly_chart(fig_entity, use_container_width=True)

    if compare_mode and ticker2:
        col_left, col_right = st.columns(2)
        render_ticker_dashboard(selected_ticker, label="Kiri: ", cols=[col_left])
        render_ticker_dashboard(ticker2, label="Kanan: ", cols=[col_right])
    else:
        render_ticker_dashboard(selected_ticker)

# =========================================================
# TAB 4: ALERT & EXPORT
# =========================================================
with tab4:
    st.subheader("🔔 Alert System: Smart Money Score & Deteksi Akumulasi Beruntun")

    df_score = compute_smart_money_score(df_sh[df_sh['Date_norm'].isin(filtered_dates) & df_sh['Price'].between(price_range[0], price_range[1])])

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        min_score = st.slider("Minimum Smart Money Score", 0, 100, 50, key="min_score")
    with col_a2:
        show_alert_count = st.number_input("Jumlah Ticker Ditampilkan", 5, 100, 30, step=5, key="alert_n")

    df_alert = df_score[df_score['Smart_Money_Score'] >= min_score].head(show_alert_count)

    if not df_alert.empty:
        st.success(f"Ditemukan {len(df_alert)} ticker dengan skor >= {min_score}")
        st.dataframe(
            df_alert.style.format({
                'Smart_Money_Score': '{:.0f}', 'Latest_Price': 'Rp {:,}',
                'Total_SM_Net_Val': '{:,.0f}', 'Total_Retail_Net_Val': '{:,.0f}'
            }).background_gradient(subset=['Smart_Money_Score'], cmap='RdYlGn'),
            use_container_width=True
        )

        # Bar chart
        fig_score = px.bar(df_alert.head(20), x='Code', y='Smart_Money_Score', color='Smart_Money_Score',
                           color_continuous_scale='RdYlGn', title="Top 20 Smart Money Score",
                           hover_data={'Total_SM_Net_Val': ':,.0f', 'Total_Retail_Net_Val': ':,.0f'})
        st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.warning("Tidak ada ticker memenuhi kriteria skor minimum.")

    # Trend Detection: Akumulasi 2+ bulan berturut
    st.markdown("---")
    st.markdown("### 📈 Trend Detection: Akumulasi Beruntun (2+ Bulan Berturut-turut)")
    st.markdown("Mendeteksi saham yang **Smart Money masuk terus menerus** dan **Ritel terus menjual** minimal 2 bulan beruntun.")

    trend_results = []
    for code, grp in df_sh[df_sh['Date_norm'].isin(filtered_dates)].groupby('Code'):
        grp = grp.sort_values('Date_norm')
        if len(grp) >= 2:
            sm_positive_months = (grp['Smart_Money_Net_Val'] > 0).sum()
            retail_negative_months = (grp['Retail_Net_Val'] < 0).sum()
            if sm_positive_months >= 2 and retail_negative_months >= 2:
                trend_results.append({
                    'Code': code, 'Type': grp['Type'].iloc[0],
                    'SM_Positive_Months': sm_positive_months,
                    'Retail_Negative_Months': retail_negative_months,
                    'Total_SM_Flow': grp['Smart_Money_Net_Val'].sum(),
                    'Total_Retail_Flow': grp['Retail_Net_Val'].sum(),
                    'Price_Trend': f"Rp {grp['Price'].iloc[0]:,.0f} → Rp {grp['Price'].iloc[-1]:,.0f}",
                    'Price_Change_%': (grp['Price'].iloc[-1] - grp['Price'].iloc[0]) / grp['Price'].iloc[0] * 100
                })

    if trend_results:
        df_trend = pd.DataFrame(trend_results).sort_values('Total_SM_Flow', ascending=False)
        st.success(f"Ditemukan {len(df_trend)} saham dengan pola akumulasi beruntun!")
        st.dataframe(
            df_trend.style.format({
                'Total_SM_Flow': '{:,.0f}', 'Total_Retail_Flow': '{:,.0f}',
                'Price_Change_%': '{:+.2f}%'
            }).background_gradient(subset=['Price_Change_%'], cmap='RdYlGn'),
            use_container_width=True
        )

        fig_trend_detect = px.scatter(df_trend, x='Total_SM_Flow', y='Price_Change_%', color='SM_Positive_Months',
                                       size='Retail_Negative_Months', hover_name='Code',
                                       title='Akumulasi Beruntun: SM Flow vs Price Change',
                                       labels={'Total_SM_Flow': 'Total Smart Money Flow (IDR)',
                                               'Price_Change_%': 'Perubahan Harga (%)'})
        st.plotly_chart(fig_trend_detect, use_container_width=True)
    else:
        st.info("Tidak ada saham dengan pola akumulasi beruntun di periode ini.")

    # Export
    st.markdown("---")
    st.markdown("### 📥 Export Data")
    if st.button("📥 Export Radar ke CSV", type="primary"):
        if not df_alert.empty:
            csv = df_alert.to_csv(index=False)
            st.download_button("Download CSV", csv, "smart_money_radar.csv", "text/csv")
        else:
            st.warning("Tidak ada data untuk diexport.")
