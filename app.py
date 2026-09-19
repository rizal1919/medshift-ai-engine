import streamlit as st
import pandas as pd
import joblib
import datetime

# 1. Konfigurasi Halaman
st.set_page_config(page_title="MedShift AI Dashboard", page_icon="🏥", layout="wide")
st.title("🏥 MedShift AI - Prediksi Keterlambatan")
st.write("Dashboard analitik untuk memprediksi probabilitas keterlambatan staf medis berdasarkan pola historis dan kondisi cuaca perkotaan.")

# 2. Load Model & Fitur
@st.cache_resource
def load_model():
    model = joblib.load('medshift_model_v2.pkl')
    fitur = joblib.load('medshift_features_v2.pkl')
    return model, fitur

try:
    model, fitur_wajib = load_model()
    st.sidebar.success("✅ Model AI Aktif (Random Forest V2)")
except Exception as e:
    st.error(f"Gagal memuat model: {e}")

# 3. Sidebar Input Parameter
st.sidebar.header("⚙️ Parameter Prediksi Harian")
shift = st.sidebar.selectbox("Shift Kerja", [1, 2, 3], help="1: Pagi, 2: Siang, 3: Malam")
rain = st.sidebar.number_input("Curah Hujan (mm)", min_value=0.0, value=0.0)
suhu = st.sidebar.number_input("Suhu Udara (°C)", min_value=20.0, value=28.5)
kelembapan = st.sidebar.number_input("Kelembapan (%)", min_value=0.0, value=75.0)

st.sidebar.markdown("---")
st.sidebar.header("👤 Profil Karyawan (Simulasi)")
riwayat_telat = st.sidebar.slider("Track Record Sering Telat", 0.0, 1.0, 0.1, help="0.0 = Selalu tepat waktu, 1.0 = Sangat sering telat")
is_weekend = st.sidebar.checkbox("Apakah hari ini Akhir Pekan (Sabtu/Minggu)?")
is_gajian = st.sidebar.checkbox("Apakah hari ini Tanggal Gajian?")
is_tanggal_tua = st.sidebar.checkbox("Apakah ini Tanggal Tua (20-24)?")

# 4. Tombol Prediksi
if st.button("🚀 Jalankan Prediksi AI", use_container_width=True):
    # Siapkan DataFrame kosong dengan kolom yang sama persis saat training (isi 0 semua)
    df_input = pd.DataFrame(columns=fitur_wajib)
    df_input.loc[0] = 0.0 
    
    # Masukkan nilai dari input pengguna ke kolom yang relevan
    df_input.at[0, 'ShiftKerja'] = shift
    df_input.at[0, 'rain'] = rain
    df_input.at[0, 'suhu'] = suhu
    df_input.at[0, 'kelembapan'] = kelembapan
    df_input.at[0, 'riwayat_telat'] = riwayat_telat
    df_input.at[0, 'is_weekend'] = 1 if is_weekend else 0
    df_input.at[0, 'is_hari_gajian'] = 1 if is_gajian else 0
    df_input.at[0, 'is_tanggal_tua'] = 1 if is_tanggal_tua else 0
    
    # Eksekusi Prediksi
    prob_telat = model.predict_proba(df_input)[0][1]
    
    # Tampilkan Hasil dengan UI yang cantik
    st.markdown("---")
    st.subheader("📊 Hasil Analisis MedShift")
    
    col1, col2 = st.columns(2)
    with col1:
        if prob_telat > 0.5:
            st.error(f"⚠️ RAWAN TERLAMBAT")
        else:
            st.success(f"✅ AMAN (ESTIMASI TEPAT WAKTU)")
            
    with col2:
        st.metric(label="Probabilitas Keterlambatan", value=f"{prob_telat * 100:.1f}%")
        
    st.info("💡 **Insight:** Model ini sangat menitikberatkan pada *Track Record* individu dan cuaca saat ini. Coba naikkan nilai curah hujan atau riwayat telat di sebelah kiri untuk melihat perubahan probabilitas secara *real-time*.")