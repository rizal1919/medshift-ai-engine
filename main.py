from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import joblib
import pandas as pd
import json
import datetime
import requests

app = FastAPI(
    title="MedShift AI Engine",
    description="API Machine Learning dengan Payload Minimalis",
    version="4.1.0"
)

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
    tanggal: str = Field(..., description="Format YYYY-MM-DD", example="2026-08-24")
    ShiftKerja: int = Field(..., description="1 (Pagi), 2 (Siang), 3 (Malam)", example=1)
    
# ==========================================
# 3. FUNGSI BANTUAN CRAWLING CUACA
# ==========================================
def get_weather_forecast(tanggal: str, shift: int):
    # Mapping shift ke perkiraan jam masuk (asumsi Shift 1=07:00, Shift 2=14:00, Shift 3=21:00)
    jam_masuk = "07:00" if shift == 1 else "14:00" if shift == 2 else "21:00"
    waktu_target = f"{tanggal}T{jam_masuk}"
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude=-7.25&longitude=112.75&hourly=temperature_2m,relative_humidity_2m,precipitation&timezone=Asia/Jakarta&start_date={tanggal}&end_date={tanggal}"
    
    try:
        resp = requests.get(url).json()
        times = resp['hourly']['time']
        # Cari indeks waktu yang cocok dengan jam masuk
        if waktu_target in times:
            idx = times.index(waktu_target)
            return {
                "suhu": resp['hourly']['temperature_2m'][idx],
                "kelembapan": resp['hourly']['relative_humidity_2m'][idx],
                "rain": resp['hourly']['precipitation'][idx]
            }
    except Exception as e:
        print(f"Gagal narik cuaca: {e}")
        
    # Default aman jika API cuaca gagal (cerah berawan)
    return {"suhu": 28.0, "kelembapan": 70.0, "rain": 0.0}

# ==========================================
# 4. ENDPOINT UTAMA (PREDIKSI)
# ==========================================
@app.post("/api/predict-besok")
def predict_besok(data: PrediksiSimpleInput):
    # --- PROSES AUTO-FILL (Backend merakit data) ---
    
    # 1. Cek Data Pegawai di JSON
    if data.npp not in master_pegawai:
        raise HTTPException(
            status_code=404, 
            detail=f"NPP {data.npp} tidak ditemukan di database master_pegawai.json"
        )
        
    unit_kerja = master_pegawai[data.npp].get("Unit_Kerja", "LAIN-LAIN")
    status_kepeg = master_pegawai[data.npp].get("Status_Kepegawaian", "Pegawai Tetap")
    
    # 2. Olah Tanggal
    tgl_obj = datetime.datetime.strptime(data.tanggal, "%Y-%m-%d")
    is_weekend = 1 if tgl_obj.weekday() >= 5 else 0
    is_hari_gajian = 1 if tgl_obj.day in [25, 26] else 0
    is_tanggal_tua = 1 if 20 <= tgl_obj.day <= 24 else 0
    nama_hari = tgl_obj.strftime('%A')
    
    # 3. Tarik Historis Karyawan dari JSON (Default 0.1 jika tidak ada riwayat)
    riwayat = kamus_riwayat.get(data.npp, 0.1)
    
    # 4. Tarik Cuaca Live
    cuaca = get_weather_forecast(data.tanggal, data.ShiftKerja)
    
    # --- RAKIT DATAFRAME LENGKAP UNTUK AI ---
    data_mentah = {
        "ShiftKerja": data.ShiftKerja,
        "suhu": cuaca["suhu"],
        "kelembapan": cuaca["kelembapan"],
        "rain": cuaca["rain"],
        "is_weekend": is_weekend,
        "is_hari_gajian": is_hari_gajian,
        "is_tanggal_tua": is_tanggal_tua,
        "riwayat_telat": riwayat,
        "Unit_Kerja": unit_kerja,
        "Status_Kepegawaian": status_kepeg,
        "nama_hari": nama_hari
    }
    
    df_input = pd.DataFrame([data_mentah])
    
    # One-Hot Encoding
    df_encoded = pd.get_dummies(df_input, columns=['Unit_Kerja', 'Status_Kepegawaian', 'nama_hari'])
    
    # Pastikan format cocok dengan cetakan model
    df_prediksi = df_encoded.reindex(columns=fitur_wajib, fill_value=0)
    
    # --- PREDIKSI! ---
    is_late = int(model.predict(df_prediksi)[0])
    prob_telat = model.predict_proba(df_prediksi)[0][1]
    
    # Heuristik Estimasi
    if is_late == 0:
        estimasi = "Tepat Waktu"
    elif prob_telat > 0.85:
        estimasi = "> 30 Menit"
    elif prob_telat > 0.65:
        estimasi = "15 - 30 Menit"
    else:
        estimasi = "< 15 Menit"
        
    return {
        "npp": data.npp,
        "tanggal": data.tanggal,
        "unit_kerja": unit_kerja,
        "status": status_kepeg,
        "cuaca_saat_shift": f"Suhu {cuaca['suhu']}°C, Hujan {cuaca['rain']}mm",
        "is_late": is_late,
        "probabilitas_telat": f"{prob_telat * 100:.1f}%",
        "estimasi_keterlambatan": estimasi
    }

# ==========================================
# 5. ENDPOINT DATA MASTER (Opsional / Legacy)
# ==========================================
@app.get("/api/master/unit-kerja", summary="Ambil Daftar Master Unit Kerja")
def get_master_unit_kerja():
    daftar_unit = [
        fitur.replace('Unit_Kerja_', '') 
        for fitur in fitur_wajib 
        if fitur.startswith('Unit_Kerja_') 
        and not fitur.replace('Unit_Kerja_', '').startswith(('DEPARTEMEN', 'DEPT.'))
    ]
    daftar_unit.sort()
    return {"total": len(daftar_unit), "data": daftar_unit}

@app.get("/api/master/shift", summary="Ambil Daftar Master Shift")
def get_master_shift():
    return {
        "data": [
            {"id": 1, "nama": "Shift Pagi (07:00)"},
            {"id": 2, "nama": "Shift Siang (14:00)"},
            {"id": 3, "nama": "Shift Malam (21:00)"}
        ]
    }

# ==========================================
# 6. ENDPOINT PELENGKAP (UTILITY)
# ==========================================
@app.get("/api/karyawan/{npp}/habit", summary="Cek Track Record Keterlambatan")
def get_karyawan_habit(npp: str):
    riwayat = kamus_riwayat.get(npp, 0.0)
    persentase = riwayat * 100
    
    if persentase > 50:
        status = "Sangat Buruk (Sering Telat)"
    elif persentase > 20:
        status = "Kurang Baik (Cukup Sering Telat)"
    elif persentase > 5:
        status = "Baik (Jarang Telat)"
    else:
        status = "Sangat Disiplin"
        
    return {
        "npp": npp,
        "riwayat_telat_value": riwayat,
        "persentase_string": f"{persentase:.1f}%",
        "status_habit": status
    }

@app.get("/api/health", summary="Cek Status Server (System Health)")
def health_check():
    import datetime
    return {
        "status": "Online",
        "service": "MedShift AI Engine",
        "version": "4.1.0",
        "model_accuracy": "84.14%",
        "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }