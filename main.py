from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from typing import List, Optional
import joblib
import pandas as pd
import json
import datetime
from datetime import timedelta, timezone
import requests
import jwt


description_text = """
# MedShift AI - Panduan Integrasi Frontend

Halo Tim Frontend! 👋
API ini dilindungi oleh otentikasi **JWT (JSON Web Token)** standar *Enterprise*. Untuk mengakses data presensi atau melakukan prediksi, ikuti 2 langkah berikut:

### LANGKAH 1: Request Access Token (Otentikasi M2M)
Sebelum menembak endpoint utama, sistem frontend wajib meminta *token* terlebih dahulu. Token ini berlaku selama 60 menit.
- **Endpoint:** `POST /api/auth/login`
- **Tipe Body:** `x-www-form-urlencoded`
- **Kredensial:**
    - `username` (Client ID): `medshift_core_app`
    - `password` (Client Secret): **[NOT THIS TIME, TRY TO HACK US!]**

### LANGKAH 2: Sisipkan Token di Headers
Setelah mendapat balasan berupa *access token*, sisipkan token tersebut di **Headers** pada setiap request ke endpoint lain.
- **Key:** `Authorization`
- **Value:** `Bearer <TOKEN_DARI_LANGKAH_1>`

#### Contoh Penggunaan (JavaScript/Fetch) untuk Tarik Data Filter Unit Kerja:
```javascript
// Karena nama unit mengandung spasi dan tanda kurung, sangat disarankan menggunakan URLSearchParams
const params = new URLSearchParams([
    ['unit', 'E.D.P. (TEKNOLOGI INFORMASI)'],
    ['unit', 'ENDOSCOPY']
]);

// URL akan otomatis terformat dengan benar
const url = `[http://103.247.10.116:8000/api/master/pegawai-filter?$](http://103.247.10.116:8000/api/master/pegawai-filter?$){params.toString()}`;

fetch(url, {
    method: 'GET',
    headers: {
        'Authorization': 'Bearer eyJhbGciOiJIUzI1...' // Ganti dengan token dari Langkah 1
    }
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error("Error API:", err));
"""

app = FastAPI(
    title="MedShift AI Engine",
    description=description_text,
    version="4.3.0"
)

# ==========================================
# 0. KONFIGURASI KEAMANAN (JWT)
# ==========================================
SECRET_KEY = "rahasia_medshift_rs_adi_husada_2026" # Key enkripsi
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 # Expired dalam 1 jam

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Kredensial tidak valid")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token sudah expired! Silakan login ulang.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token rusak atau tidak valid.")

# ==========================================
# 1. LOAD MODEL & DATA MASTER
# ==========================================
model = joblib.load('medshift_model_v2.pkl')
fitur_wajib = joblib.load('medshift_features_v2.pkl')

try:
    with open('kamus_riwayat.json', 'r') as f:
        kamus_riwayat = json.load(f)
except FileNotFoundError:
    kamus_riwayat = {}
    print("Warning: kamus_riwayat.json tidak ditemukan. Akan menggunakan default 0.0")

try:
    with open('master_pegawai.json', 'r') as f:
        master_pegawai = json.load(f)
except FileNotFoundError:
    master_pegawai = {}
    print("Warning: master_pegawai.json tidak ditemukan. Pastikan file JSON sudah di-generate.")

# ==========================================
# 2. SKEMA PAYLOAD (Super Ringkas)
# ==========================================
class PrediksiSimpleInput(BaseModel):
    npp: str = Field(..., example="2365")
    tanggal: str = Field(..., description="Format YYYY-MM-DD", example="2026-10-24")
    ShiftKerja: int = Field(..., description="1 (Pagi), 2 (Siang), 3 (Malam)", example=1)

class PrediksiBulkInput(BaseModel):
    npps: List[str] = Field(..., example=["2365", "0652", "0718"])
    tanggal: str = Field(..., description="Format YYYY-MM-DD", example="2026-10-25")
    ShiftKerja: int = Field(..., description="1 (Pagi), 2 (Siang), 3 (Malam)", example=1)
    
# ==========================================
# 3. FUNGSI BANTUAN CRAWLING CUACA
# ==========================================
def get_weather_forecast(tanggal: str, shift: int):
    jam_masuk = "07:00" if shift == 1 else "14:00" if shift == 2 else "21:00"
    waktu_target = f"{tanggal}T{jam_masuk}"
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude=-7.25&longitude=112.75&hourly=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia/Jakarta&start_date={tanggal}&end_date={tanggal}"
    
    try:
        resp = requests.get(url).json()
        times = resp['hourly']['time']
        if waktu_target in times:
            idx = times.index(waktu_target)
            return {
                "suhu": resp['hourly']['temperature_2m'][idx],
                "kelembapan": resp['hourly']['relative_humidity_2m'][idx],
                "rain": resp['hourly']['precipitation'][idx]
            }
    except Exception as e:
        print(f"Gagal narik cuaca: {e}")
        
    return {"suhu": 28.0, "kelembapan": 70.0, "rain": 0.0}

# ==========================================
# 4. ENDPOINT OTORISASI LOGIN
# ==========================================
@app.post("/api/auth/login", summary="Otentikasi Sistem (Dapatkan Access Token)")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Di dunia profesional, 'username' bertindak sebagai Client ID 
    # dan 'password' bertindak sebagai Client Secret
    CLIENT_ID = "medshift_core_app"
    CLIENT_SECRET = "Capstone_Medshift@2026!"
    
    if form_data.username != CLIENT_ID or form_data.password != CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Client ID atau Client Secret tidak valid")
        
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, 
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# ==========================================
# 5. ENDPOINT UTAMA (PREDIKSI) -> DILINDUNGI TOKEN
# ==========================================
@app.post("/api/predict-besok", summary="Prediksi Individu")
def predict_besok(data: PrediksiSimpleInput, current_user: str = Depends(verify_token)):
    if data.npp not in master_pegawai:
        raise HTTPException(status_code=404, detail=f"NPP {data.npp} tidak ditemukan")
        
    # --- PEMBERSIHAN NaN ---
    unit_kerja = str(master_pegawai[data.npp].get("Unit_Kerja", "LAIN-LAIN")).strip()
    status_kepeg = str(master_pegawai[data.npp].get("Status_Kepegawaian", "Pegawai Tetap")).strip()
    nama_pegawai = str(master_pegawai[data.npp].get("nama", "Tidak Diketahui")).strip()
    kd_bagian = str(master_pegawai[data.npp].get("kd_bagian", "TIDAK ADA")).strip()
    
    unit_kerja = "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja
    status_kepeg = "Pegawai Tetap" if status_kepeg.lower() == "nan" else status_kepeg
    nama_pegawai = "Tidak Diketahui" if nama_pegawai.lower() == "nan" else nama_pegawai
    kd_bagian = "TIDAK ADA" if kd_bagian.lower() == "nan" else kd_bagian
    # -----------------------
    
    tgl_obj = datetime.datetime.strptime(data.tanggal, "%Y-%m-%d")
    is_weekend = 1 if tgl_obj.weekday() >= 5 else 0
    is_hari_gajian = 1 if tgl_obj.day in [25, 26] else 0
    is_tanggal_tua = 1 if 20 <= tgl_obj.day <= 24 else 0
    nama_hari = tgl_obj.strftime('%A')
    
    riwayat = kamus_riwayat.get(data.npp, 0.1)
    cuaca = get_weather_forecast(data.tanggal, data.ShiftKerja)
    
    data_mentah = {
        "ShiftKerja": data.ShiftKerja, "suhu": cuaca["suhu"], "kelembapan": cuaca["kelembapan"],
        "rain": cuaca["rain"], "is_weekend": is_weekend, "is_hari_gajian": is_hari_gajian,
        "is_tanggal_tua": is_tanggal_tua, "riwayat_telat": riwayat, "Unit_Kerja": unit_kerja,
        "Status_Kepegawaian": status_kepeg, "nama_hari": nama_hari
    }
    
    df_input = pd.DataFrame([data_mentah])
    df_encoded = pd.get_dummies(df_input, columns=['Unit_Kerja', 'Status_Kepegawaian', 'nama_hari'])
    df_prediksi = df_encoded.reindex(columns=fitur_wajib, fill_value=0)
    
    is_late = int(model.predict(df_prediksi)[0])
    prob_telat = model.predict_proba(df_prediksi)[0][1]
    
    if is_late == 0: estimasi = "Tepat Waktu"
    elif prob_telat > 0.85: estimasi = "> 30 Menit"
    elif prob_telat > 0.65: estimasi = "15 - 30 Menit"
    else: estimasi = "< 15 Menit"
        
    return {
        "npp": str(data.npp), 
        "nama": nama_pegawai, 
        "kd_bagian": kd_bagian,
        "tanggal": data.tanggal,
        "unit_kerja": unit_kerja, 
        "status": status_kepeg,
        "cuaca_saat_shift": f"Suhu {cuaca['suhu']}°C, Hujan {cuaca['rain']}mm",
        "is_late": is_late, 
        "probabilitas_telat": f"{prob_telat * 100:.1f}%",
        "estimasi_keterlambatan": estimasi
    }


@app.post("/api/predict-bulk", summary="Prediksi Massal (Banyak NPP Sekaligus)")
def predict_bulk(data: PrediksiBulkInput, current_user: str = Depends(verify_token)):
    cuaca = get_weather_forecast(data.tanggal, data.ShiftKerja)
    tgl_obj = datetime.datetime.strptime(data.tanggal, "%Y-%m-%d")
    is_weekend = 1 if tgl_obj.weekday() >= 5 else 0
    is_hari_gajian = 1 if tgl_obj.day in [25, 26] else 0
    is_tanggal_tua = 1 if 20 <= tgl_obj.day <= 24 else 0
    nama_hari = tgl_obj.strftime('%A')
    
    data_mentah_list = []
    hasil_respon = []
    npp_valid = []
    
    for npp in data.npps:
        if npp not in master_pegawai:
            hasil_respon.append({"npp": str(npp), "error": "NPP tidak ditemukan"})
            continue
            
        # --- PEMBERSIHAN NaN UNTUK AI ---
        unit_kerja = str(master_pegawai[npp].get("Unit_Kerja", "LAIN-LAIN")).strip()
        status_kepeg = str(master_pegawai[npp].get("Status_Kepegawaian", "Pegawai Tetap")).strip()
        
        unit_kerja = "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja
        status_kepeg = "Pegawai Tetap" if status_kepeg.lower() == "nan" else status_kepeg
        # --------------------------------
        
        riwayat = kamus_riwayat.get(npp, 0.1)
        
        data_mentah = {
            "ShiftKerja": data.ShiftKerja, "suhu": cuaca["suhu"], "kelembapan": cuaca["kelembapan"],
            "rain": cuaca["rain"], "is_weekend": is_weekend, "is_hari_gajian": is_hari_gajian,
            "is_tanggal_tua": is_tanggal_tua, "riwayat_telat": riwayat, "Unit_Kerja": unit_kerja,
            "Status_Kepegawaian": status_kepeg, "nama_hari": nama_hari
        }
        data_mentah_list.append(data_mentah)
        npp_valid.append(npp)
        
    if not data_mentah_list:
        return {"pesan": "Semua NPP yang dikirim tidak ditemukan", "hasil": hasil_respon}
        
    df_input = pd.DataFrame(data_mentah_list)
    df_encoded = pd.get_dummies(df_input, columns=['Unit_Kerja', 'Status_Kepegawaian', 'nama_hari'])
    df_prediksi = df_encoded.reindex(columns=fitur_wajib, fill_value=0)
    
    prediksi_labels = model.predict(df_prediksi)
    prediksi_probs = model.predict_proba(df_prediksi)[:, 1]
    
    for i, npp in enumerate(npp_valid):
        is_late = int(prediksi_labels[i])
        prob_telat = prediksi_probs[i]
        
        if is_late == 0: estimasi = "Tepat Waktu"
        elif prob_telat > 0.85: estimasi = "> 30 Menit"
        elif prob_telat > 0.65: estimasi = "15 - 30 Menit"
        else: estimasi = "< 15 Menit"
            
        # --- PEMBERSIHAN NaN UNTUK RESPONSE JSON ---
        unit_kerja = str(master_pegawai[npp].get("Unit_Kerja", "LAIN-LAIN")).strip()
        status_kepeg = str(master_pegawai[npp].get("Status_Kepegawaian", "Pegawai Tetap")).strip()
        nama_pegawai = str(master_pegawai[npp].get("nama", "Tidak Diketahui")).strip()
        kd_bagian = str(master_pegawai[npp].get("kd_bagian", "TIDAK ADA")).strip()
        
        unit_kerja = "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja
        status_kepeg = "Pegawai Tetap" if status_kepeg.lower() == "nan" else status_kepeg
        nama_pegawai = "Tidak Diketahui" if nama_pegawai.lower() == "nan" else nama_pegawai
        kd_bagian = "TIDAK ADA" if kd_bagian.lower() == "nan" else kd_bagian
        # -------------------------------------------
            
        hasil_respon.append({
            "npp": str(npp), 
            "nama": nama_pegawai, 
            "kd_bagian": kd_bagian,
            "unit_kerja": unit_kerja, 
            "status": status_kepeg,
            "is_late": is_late, 
            "probabilitas_telat": f"{prob_telat * 100:.1f}%",
            "estimasi_keterlambatan": estimasi
        })
        
    return {
        "tanggal": data.tanggal, "shift": data.ShiftKerja,
        "cuaca": f"Suhu {cuaca['suhu']}°C, Hujan {cuaca['rain']}mm",
        "total_diproses": len(data.npps), "hasil_prediksi": hasil_respon
    }

@app.get("/api/predict-all-grouped", summary="Prediksi SELURUH Pegawai (Di-Group by Estimasi)")
def predict_all_grouped(
    tanggal: str = Query(..., description="Format YYYY-MM-DD", example="2026-08-25"),
    shift: int = Query(..., description="1 (Pagi), 2 (Siang), 3 (Malam)", example=1),
    current_user: str = Depends(verify_token)
):
    # 1. Tarik cuaca dan tanggal
    cuaca = get_weather_forecast(tanggal, shift)
    tgl_obj = datetime.datetime.strptime(tanggal, "%Y-%m-%d")
    is_weekend = 1 if tgl_obj.weekday() >= 5 else 0
    is_hari_gajian = 1 if tgl_obj.day in [25, 26] else 0
    is_tanggal_tua = 1 if 20 <= tgl_obj.day <= 24 else 0
    nama_hari = tgl_obj.strftime('%A')
    
    data_mentah_list = []
    npp_valid = []
    
    # 2. Siapkan keranjang hasil
    hasil_group = {
        "Tepat Waktu": [],
        "< 15 Menit": [],
        "15 - 30 Menit": [],
        "> 30 Menit": []
    }
    
    # 3. Looping SEMUA data di master_pegawai
    for npp, info in master_pegawai.items():
        # --- PEMBERSIHAN NaN UNTUK AI ---
        unit_kerja = str(info.get("Unit_Kerja", "LAIN-LAIN")).strip()
        status_kepeg = str(info.get("Status_Kepegawaian", "Pegawai Tetap")).strip()
        
        unit_kerja = "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja
        status_kepeg = "Pegawai Tetap" if status_kepeg.lower() == "nan" else status_kepeg
        
        riwayat = kamus_riwayat.get(npp, 0.1)
        
        data_mentah = {
            "ShiftKerja": shift, "suhu": cuaca["suhu"], "kelembapan": cuaca["kelembapan"],
            "rain": cuaca["rain"], "is_weekend": is_weekend, "is_hari_gajian": is_hari_gajian,
            "is_tanggal_tua": is_tanggal_tua, "riwayat_telat": riwayat, "Unit_Kerja": unit_kerja,
            "Status_Kepegawaian": status_kepeg, "nama_hari": nama_hari
        }
        data_mentah_list.append(data_mentah)
        npp_valid.append(npp)
        
    # Jika database kebetulan kosong
    if not data_mentah_list:
        return {"pesan": "Database pegawai kosong", "hasil": hasil_group}
        
    # 4. Prediksi Sekaligus (Super Cepat dengan Pandas)
    df_input = pd.DataFrame(data_mentah_list)
    df_encoded = pd.get_dummies(df_input, columns=['Unit_Kerja', 'Status_Kepegawaian', 'nama_hari'])
    df_prediksi = df_encoded.reindex(columns=fitur_wajib, fill_value=0)
    
    prediksi_labels = model.predict(df_prediksi)
    prediksi_probs = model.predict_proba(df_prediksi)[:, 1]
    
    # 5. Kelompokkan ke keranjang masing-masing
    for i, npp in enumerate(npp_valid):
        is_late = int(prediksi_labels[i])
        prob_telat = prediksi_probs[i]
        
        if is_late == 0: 
            estimasi = "Tepat Waktu"
        elif prob_telat > 0.85: 
            estimasi = "> 30 Menit"
        elif prob_telat > 0.65: 
            estimasi = "15 - 30 Menit"
        else: 
            estimasi = "< 15 Menit"
            
        # --- PEMBERSIHAN NaN UNTUK RESPONSE JSON ---
        info = master_pegawai[npp]
        nama_pegawai = str(info.get("nama", "Tidak Diketahui")).strip()
        kd_bagian = str(info.get("kd_bagian", "TIDAK ADA")).strip()
        unit_kerja = str(info.get("Unit_Kerja", "LAIN-LAIN")).strip()
        
        nama_pegawai = "Tidak Diketahui" if nama_pegawai.lower() == "nan" else nama_pegawai
        kd_bagian = "TIDAK ADA" if kd_bagian.lower() == "nan" else kd_bagian
        unit_kerja = "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja
            
        hasil_group[estimasi].append({
            "npp": str(npp), 
            "nama": nama_pegawai, 
            "kd_bagian": kd_bagian,
            "unit_kerja": unit_kerja,
            "probabilitas_telat": f"{prob_telat * 100:.1f}%"
        })
        
    # 6. Susun Output Final
    return {
        "tanggal": tanggal, 
        "shift": shift,
        "cuaca": f"Suhu {cuaca['suhu']}°C, Hujan {cuaca['rain']}mm",
        "ringkasan": {
            "total_karyawan_diproses": len(npp_valid),
            "jumlah_aman": len(hasil_group["Tepat Waktu"]),
            "jumlah_rawan_telat": len(hasil_group["< 15 Menit"]) + len(hasil_group["15 - 30 Menit"]) + len(hasil_group["> 30 Menit"])
        },
        "data_kategori": hasil_group
    }


# ==========================================
# 6. ENDPOINT DATA MASTER (Terproteksi JWT)
# ==========================================
@app.get("/api/master/pegawai", summary="Ambil Daftar SEMUA Pegawai (Tanpa Filter)")
def get_semua_pegawai(current_user: str = Depends(verify_token)):
    daftar_pegawai = []
    
    for npp, info in master_pegawai.items():
        # 1. Bungkus semua jadi string (str) agar NaN bawaan Pandas berubah jadi teks "nan"
        nama = str(info.get("nama", "Tidak Diketahui")).strip()
        kd_bagian = str(info.get("kd_bagian", "TIDAK ADA")).strip()
        unit_kerja = str(info.get("Unit_Kerja", "LAIN-LAIN")).strip()
        status_pegawai = str(info.get("Status_Kepegawaian", "Pegawai Tetap")).strip()
        
        # 2. Jika isinya "nan", ubah jadi teks yang rapi agar frontend tidak bingung
        daftar_pegawai.append({
            "npp": str(npp),
            "nama": "Tidak Diketahui" if nama.lower() == "nan" else nama,
            "kd_bagian": "TIDAK ADA" if kd_bagian.lower() == "nan" else kd_bagian,
            "unit_kerja": "LAIN-LAIN" if unit_kerja.lower() == "nan" else unit_kerja,
            "status": "Pegawai Tetap" if status_pegawai.lower() == "nan" else status_pegawai
        })
        
    return {
        "total_pegawai": len(daftar_pegawai),
        "data": daftar_pegawai
    }

@app.get("/api/master/pegawai-filter", summary="Ambil Daftar Pegawai (Filter by Kode Bagian)")
def get_pegawai_filter(
    kd_bagian: List[str] = Query(
        None, 
        description="Filter berdasarkan Kode Bagian. Klik 'Add string item' untuk menggabungkan banyak kode.",
        example=["E.D.P. (TEKNOLOGI INFORMASI)']", "ENDOSCOPY"] # <--- Sesuaikan dengan contoh kode bagian aslimu
    ),
    current_user: str = Depends(verify_token)
):
    daftar_pegawai = []
    
    # Bersihkan spasi dan pastikan huruf besar semua agar cocok 100%
    clean_kd = [k.strip().upper() for k in kd_bagian] if kd_bagian else []
    
    for npp, info in master_pegawai.items():
        # Tarik kd_bagian dari JSON
        kd_asli = str(info.get("kd_bagian", "")).strip().upper()
        
        # Logika Filter: Jika tidak ada filter, atau kd_asli ada di dalam daftar request frontend
        if not clean_kd or kd_asli in clean_kd:
            daftar_pegawai.append({
                "npp": npp,
                "nama": info.get("nama", "Tidak Diketahui"),
                "kd_bagian": info.get("kd_bagian", "TIDAK ADA"),
                "unit_kerja": info.get("Unit_Kerja", "LAIN-LAIN"),
                "status": info.get("Status_Kepegawaian", "Pegawai Tetap")
            })
            
    return {
        "total_pegawai": len(daftar_pegawai),
        "filter_aktif": clean_kd if clean_kd else "Semua Bagian",
        "data": daftar_pegawai
    }

@app.get("/api/master/unit-kerja", summary="Ambil Daftar Master Unit Kerja & Kode Bagian")
def get_master_unit_kerja(current_user: str = Depends(verify_token)):
    # Mengumpulkan pasangan unik kd_bagian dan Unit_Kerja dari JSON
    unit_unik = {}
    
    for info in master_pegawai.values():
        kd = str(info.get("kd_bagian", "")).strip().upper()
        nama_unit = str(info.get("Unit_Kerja", "LAIN-LAIN")).strip()
        
        # Abaikan data yang kosong atau bernilai 'nan' (bawaan Pandas)
        if kd and kd != "NAN":
            unit_unik[kd] = nama_unit
            
    # Format ke dalam bentuk list supaya gampang dibaca oleh frontend
    daftar_unit = [
        {"kd_bagian": k, "unit_kerja": v} 
        for k, v in unit_unik.items()
    ]
    
    # Urutkan berdasarkan abjad kd_bagian agar rapi
    daftar_unit.sort(key=lambda x: x["kd_bagian"])
    
    return {"total": len(daftar_unit), "data": daftar_unit}

# ==========================================
# 7. ENDPOINT PELENGKAP (UTILITY)
# ==========================================
@app.get("/api/karyawan/{npp}/habit", summary="Cek Track Record Keterlambatan")
def get_karyawan_habit(npp: str, current_user: str = Depends(verify_token)):
    riwayat = kamus_riwayat.get(npp, 0.0)
    persentase = riwayat * 100
    
    if persentase > 50: status = "Sangat Buruk (Sering Telat)"
    elif persentase > 20: status = "Kurang Baik (Cukup Sering Telat)"
    elif persentase > 5: status = "Baik (Jarang Telat)"
    else: status = "Sangat Disiplin"
        
    return {
        "npp": npp, "riwayat_telat_value": riwayat,
        "persentase_string": f"{persentase:.1f}%", "status_habit": status
    }

@app.get("/api/health", summary="Cek Status Server (Terbuka untuk Ping)")
def health_check():
    return {
        "status": "Online", "service": "MedShift AI Engine", "version": "4.3.0",
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "security": "JWT Active"
    }












