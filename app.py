import streamlit as st
import pandas as pd
import joblib

# 1. Konfigurasi Halaman
st.set_page_config(page_title="MedShift AI Dashboard", page_icon="🏥", layout="wide")
st.title("🏥 MedShift AI - Prediksi Keterlambatan")
st.write("Dashboard analitik untuk memprediksi probabilitas keterlambatan staf medis berdasarkan pola historis, operasional, dan cuaca.")

# 2. Load Model & Fitur
@st.cache_resource
def load_model():
    # Ubah nama file di bawah ini menjadi v2
    model = joblib.load('medshift_model_v2.pkl') 
    fitur = joblib.load('medshift_features_v2.pkl')
    return model, fitur

try:
    model, fitur_wajib = load_model()
    st.sidebar.success("✅ Model AI Ultimate Aktif")
except Exception as e:
    st.error(f"Gagal memuat model. Pastikan file .pkl ada di folder yang sama. Error: {e}")
    st.stop()

# Ekstrak daftar Unit Kerja dari fitur (membuang awalan 'Unit_Kerja_')
daftar_unit = [f.replace('Unit_Kerja_', '') for f in fitur_wajib if f.startswith('Unit_Kerja_')]

# 3. Sidebar Input Parameter
st.sidebar.header("⚙️ Parameter Operasional & Cuaca")

# Shift Kerja dengan Teks Jelas
shift_opsi = {
    "Pagi (07:00 - 14:00)": 1,
    "Siang (14:00 - 21:00)": 2,
    "Malam (21:00 - 07:00)": 3
}
shift_label = st.sidebar.selectbox("Jadwal Shift Kerja", list(shift_opsi.keys()))
shift_val = shift_opsi[shift_label]

# Dropdown Unit Kerja
unit_kerja = st.sidebar.selectbox("Pilih Unit Kerja", ["Lainnya / Unit Umum"] + daftar_unit)

# Parameter Cuaca dengan interval (step) yang tidak menyusahkan
rain = st.sidebar.number_input("Curah Hujan (mm)", min_value=0.0, value=0.0, step=2.0)
suhu = st.sidebar.number_input("Suhu Udara (°C)", min_value=20.0, value=28.0, step=0.5)
kelembapan = st.sidebar.number_input("Kelembapan (%)", min_value=0.0, max_value=100.0, value=75.0, step=5.0)

st.sidebar.markdown("---")
st.sidebar.header("👤 Profil & Kondisi Karyawan")

# Track Record dalam bentuk Persentase
riwayat_telat_persen = st.sidebar.slider("Track Record Sering Telat (%)", 0, 100, 10, step=5, help="0% = Selalu on-time, 100% = Selalu telat")
riwayat_telat = riwayat_telat_persen / 100.0 # Konversi ke desimal untuk AI

# Fitur Fatigue & Streak
hari_beruntun = st.sidebar.number_input("Hari Kerja Beruntun (Streak)", min_value=1, value=1, step=1)
is_fatigue = st.sidebar.checkbox("Indikasi Kelelahan Rotasi (Shift Fatigue)?")

# Fitur Kalender
is_weekend = st.sidebar.checkbox("Apakah Akhir Pekan (Sabtu/Minggu)?")
is_gajian = st.sidebar.checkbox("Apakah Tanggal Gajian?")

# 4. Tombol Prediksi
if st.button("🚀 Analisis Probabilitas Keterlambatan", use_container_width=True):
    # Siapkan DataFrame dengan 0 untuk semua kolom
    df_input = pd.DataFrame(columns=fitur_wajib)
    df_input.loc[0] = 0.0 
    
    # Suntikkan input pengguna (pengecekan if untuk toleransi nama kolom)
    if 'shift' in df_input.columns: df_input.at[0, 'shift'] = shift_val
    if 'ShiftKerja' in df_input.columns: df_input.at[0, 'ShiftKerja'] = shift_val
    if 'rain' in df_input.columns: df_input.at[0, 'rain'] = rain
    if 'suhu' in df_input.columns: df_input.at[0, 'suhu'] = suhu
    if 'kelembapan' in df_input.columns: df_input.at[0, 'kelembapan'] = kelembapan
    if 'riwayat_telat' in df_input.columns: df_input.at[0, 'riwayat_telat'] = riwayat_telat
    if 'hari_beruntun' in df_input.columns: df_input.at[0, 'hari_beruntun'] = hari_beruntun
    if 'is_fatigue' in df_input.columns: df_input.at[0, 'is_fatigue'] = 1 if is_fatigue else 0
    if 'is_weekend' in df_input.columns: df_input.at[0, 'is_weekend'] = 1 if is_weekend else 0
    if 'is_hari_gajian' in df_input.columns: df_input.at[0, 'is_hari_gajian'] = 1 if is_gajian else 0
    
    # Suntikkan Unit Kerja (One-Hot Encoding)
    unit_col = f"Unit_Kerja_{unit_kerja}"
    if unit_col in df_input.columns:
        df_input.at[0, unit_col] = 1.0
        
    # Eksekusi Prediksi
    prob_telat = model.predict_proba(df_input)[0][1]
    
    # 5. Tampilkan Hasil
    st.markdown("---")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📊 Status Prediksi")
        if prob_telat > 0.5:
            st.error(f"⚠️ RAWAN TERLAMBAT")
        else:
            st.success(f"✅ AMAN (ESTIMASI TEPAT WAKTU)")
        
        st.write(f"**Probabilitas Keterlambatan: {prob_telat * 100:.1f}%**")
        st.progress(float(prob_telat))
        
    with col2:
        st.subheader("🧠 Kompas Keputusan AI")
        st.write("Faktor apa yang paling memberatkan keputusan ini?")
        
        # Tarik Feature Importance dari model
        importances = pd.Series(model.feature_importances_, index=fitur_wajib).sort_values(ascending=False)
        
        # Ambil 5 faktor teratas dan bersihkan namanya agar rapi
        top_5 = importances.head(5)
        top_5.index = top_5.index.str.replace('Unit_Kerja_', 'Unit: ')
        
        # Render chart native streamlit
        st.bar_chart(top_5, horizontal=True)