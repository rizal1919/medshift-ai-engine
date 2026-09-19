# 🏥 MedShift AI - Machine Learning Dashboard

Repositori ini berisi *dashboard* interaktif berbasis **Streamlit** untuk mendemonstrasikan model prediksi keterlambatan staf medis. Proyek ini merupakan bagian dari sub-sistem *Data Science* dalam **Capstone Project MedShift AI**.

*(Untuk melihat arsitektur Full-Stack meliputi FastAPI dan React, silakan kunjungi repositori utama tim kami).*

## 🧠 Tentang Model Machine Learning
Otak dari prediksi ini menggunakan algoritma **Random Forest Classifier** yang telah dioptimasi dengan teknik *Feature Engineering* (seperti penghitungan *track record* keterlambatan, indikator kelelahan shift, dan siklus finansial).

* **Akurasi Model:** ~77.88% (Model Seimbang / V3)
* **Faktor Utama:** Riwayat kedisiplinan individu, Jadwal Shift, Kondisi Cuaca (Hujan), Suhu, dan Kelembapan.
* **Validasi Eksternal:** Melalui A/B Testing (Chi-Square), kondisi cuaca perkotaan (hujan) terbukti secara statistik (P-Value 0.0000) signifikan meningkatkan probabilitas keterlambatan.

## 📂 Struktur File
* `app.py` — Skrip utama UI Dashboard Streamlit.
* `medshift_model_v2.pkl` — Model AI Random Forest yang sudah dilatih.
* `medshift_features_v2.pkl` — Daftar fitur kolom untuk sinkronisasi input.
* `requirements.txt` — Dependensi library Python.

## 🚀 Cara Menjalankan Secara Lokal

1. **Clone repositori ini:**
   ```bash
   git clone [https://github.com/username-anda/medshift-streamlit.git](https://github.com/username-anda/medshift-streamlit.git)
   cd medshift-streamlit
   ```
2. **Instal dependensi:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Jalankan aplikasi Streamlit:**
   ```bash
   streamlit run app.py
   ```
