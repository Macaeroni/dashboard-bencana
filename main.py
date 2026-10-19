"""
Dashboard Pemantauan Bencana - Kabupaten Bogor

Cara jalan:
    pip install streamlit pandas numpy plotly
    streamlit run main.py

Data yang dipakai:
- CSV kejadian bencana (format laporan BPBD, atau format sederhana
  dengan kolom tanggal, jenis_bencana, kecamatan)
- CSV meteorologi (minimal kolom curah hujan; kecamatan dari kolom
  atau dari nama file)
Kalau tidak ada file yang diunggah, dipakai data simulasi.

Catatan: koordinat kecamatan cuma perkiraan, keparahan dan indeks
risiko adalah proksi (bukan angka resmi BNPB).
"""

import base64
import os
import re
from io import StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Dashboard Bencana - Kabupaten Bogor",
    page_icon="🌧️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# Konstanta
# ---------------------------------------------------------------

TYPE_COLUMN_MAP = {
    "BANJIR": "Banjir",
    "TANAH LONGSOR": "Tanah Longsor",
    "KARHUTLA": "Karhutla",
    "ANGIN KENCANG": "Angin Kencang",
    "KEKERINGAN": "Kekeringan",
    "GERAKAN TANAH": "Gerakan Tanah",
    "GEMPABUMI": "Gempa Bumi",
    "NON ALAM": "Non Alam",
}
PALETTE = {
    "Banjir": "#3FA79E",
    "Tanah Longsor": "#D9A441",
    "Karhutla": "#E1863C",
    "Angin Kencang": "#8E8CD8",
    "Kekeringan": "#C49A6C",
    "Gerakan Tanah": "#A8763F",
    "Gempa Bumi": "#E8543F",
    "Non Alam": "#6B7A8F",
    "Tidak Diketahui": "#8A96A5",
}
# jenis bencana yang berkaitan dengan cuaca, dipakai di grafik korelasi
HIDROMETEOROLOGI = ["Banjir", "Tanah Longsor", "Angin Kencang", "Kekeringan"]
RISK_COLOR = {"Rendah": "#3FA79E", "Sedang": "#D9A441", "Tinggi": "#E8543F"}
STATUS_OPTIONS = ["Siaga Darurat", "Tanggap Darurat", "Pemantauan", "Selesai"]

NAMA_BULAN = {
    1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
    7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember",
}

LOGO_DIR = "logos"
PETA_ANALISIS_DIR = "peta_analisis"
JENIS_PETA_2026 = ["Banjir", "Tanah Longsor", "Kebakaran", "Kekeringan", "Angin Kencang", "Karhutla"]

# isi kalau mau ditampilkan di halaman Home
TIM_PENYUSUN = []
KONTAK_EMAIL = ""

# koordinat titik tengah kecamatan (perkiraan kasar)
KECAMATAN_BOGOR = [
    {"n": "Cibinong", "lat": -6.4817, "lon": 106.8540},
    {"n": "Gunung Putri", "lat": -6.4400, "lon": 106.9250},
    {"n": "Citeureup", "lat": -6.4850, "lon": 106.8850},
    {"n": "Sukaraja", "lat": -6.5600, "lon": 106.8300},
    {"n": "Babakan Madang", "lat": -6.5700, "lon": 106.8900},
    {"n": "Jonggol", "lat": -6.4550, "lon": 107.0450},
    {"n": "Cileungsi", "lat": -6.4100, "lon": 106.9700},
    {"n": "Cariu", "lat": -6.4300, "lon": 107.1500},
    {"n": "Sukamakmur", "lat": -6.5900, "lon": 107.0700},
    {"n": "Parung", "lat": -6.4050, "lon": 106.7350},
    {"n": "Gunung Sindur", "lat": -6.3600, "lon": 106.7100},
    {"n": "Kemang", "lat": -6.4900, "lon": 106.7350},
    {"n": "Bojonggede", "lat": -6.4600, "lon": 106.8100},
    {"n": "Leuwiliang", "lat": -6.5600, "lon": 106.6300},
    {"n": "Ciampea", "lat": -6.5600, "lon": 106.6900},
    {"n": "Cibungbulang", "lat": -6.5450, "lon": 106.6600},
    {"n": "Pamijahan", "lat": -6.6100, "lon": 106.6800},
    {"n": "Rumpin", "lat": -6.4550, "lon": 106.5900},
    {"n": "Jasinga", "lat": -6.5300, "lon": 106.4700},
    {"n": "Parung Panjang", "lat": -6.3800, "lon": 106.5200},
    {"n": "Nanggung", "lat": -6.6200, "lon": 106.5800},
    {"n": "Cigudeg", "lat": -6.5400, "lon": 106.4900},
    {"n": "Tenjo", "lat": -6.4400, "lon": 106.4700},
    {"n": "Ciawi", "lat": -6.6350, "lon": 106.8500},
    {"n": "Cisarua", "lat": -6.6900, "lon": 106.9500},
    {"n": "Megamendung", "lat": -6.6700, "lon": 106.9200},
    {"n": "Caringin", "lat": -6.6600, "lon": 106.8300},
    {"n": "Cijeruk", "lat": -6.6650, "lon": 106.8000},
    {"n": "Ciomas", "lat": -6.6100, "lon": 106.7700},
    {"n": "Dramaga", "lat": -6.5600, "lon": 106.7300},
    {"n": "Tamansari", "lat": -6.6250, "lon": 106.7500},
    {"n": "Klapanunggal", "lat": -6.4500, "lon": 106.9600},
    {"n": "Ciseeng", "lat": -6.4200, "lon": 106.6900},
    {"n": "Rancabungur", "lat": -6.5000, "lon": 106.7350},
    {"n": "Sukajaya", "lat": -6.6100, "lon": 106.5000},
    {"n": "Tanjungsari", "lat": -6.6350, "lon": 106.9100},
    {"n": "Tajurhalang", "lat": -6.4700, "lon": 106.7900},
    {"n": "Cigombong", "lat": -6.7150, "lon": 106.8200},
    {"n": "Leuwisadeng", "lat": -6.5750, "lon": 106.6100},
    {"n": "Tenjolaya", "lat": -6.6000, "lon": 106.7000},
]
MAP_CENTER = {"lat": -6.55, "lon": 106.80}
MAP_ZOOM = 9.4

# ---------------------------------------------------------------
# CSS
# ---------------------------------------------------------------

st.markdown(
    """
<style>
html, body, .stApp { font-family: 'IBM Plex Sans', sans-serif; }
button[data-baseweb="tab"] { white-space: nowrap !important; height: auto !important; min-height: 44px !important; }
[data-baseweb="tab-list"] { overflow-x: auto !important; flex-wrap: nowrap !important; height: auto !important; }
[data-baseweb="tab-highlight"] { height: 2.5px !important; }
.block-container {
    padding: 3.5rem 3rem 3rem 3rem; max-width: 1360px; position: relative;
}
/* logo di kanan atas, sejajar tab */
div[data-testid="stElementContainer"]:has(.logo-bar),
.element-container:has(.logo-bar) {
    position: absolute; top: 3.5rem; right: 3rem; height: 44px; width: auto; z-index: 5;
}
.logo-bar { display: flex; align-items: center; justify-content: flex-end; gap: 14px; height: 44px; }
.logo-bar img { height: 28px; width: auto; object-fit: contain; }
div[data-testid="stMetric"] {
    background: rgba(127,127,127,0.06);
    border: 1px solid rgba(127,127,127,0.18);
    border-radius: 10px; padding: 12px 16px 8px;
}
div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p, div[data-testid="stMetricLabel"] div {
    font-size: 0.8rem; opacity: 0.75; white-space: normal !important;
    overflow: visible !important; text-overflow: clip !important; line-height: 1.25;
}
div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] div {
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important; line-height: 1.2;
}
h1, h2, h3 { font-family: 'IBM Plex Sans', sans-serif; font-weight: 600; }
.dash-caption { color: rgba(127,127,127,0.9); font-size: 0.85rem; margin-top: -8px; }
.proto-note {
    border: 1px dashed rgba(127,127,127,0.35); border-radius: 10px;
    padding: 10px 14px; font-size: 0.85rem; opacity: 0.85; margin-bottom: 1rem;
}
.hero {
    border: 1px solid rgba(127,127,127,0.22); border-radius: 14px;
    padding: 30px 32px 26px; margin: 0.4rem 0 1.6rem;
    background: linear-gradient(135deg, rgba(63,167,158,0.14), rgba(232,84,63,0.07));
}
.hero-kicker { font-size: 0.85rem; opacity: 0.75; margin-bottom: 6px; }
.hero-title { font-size: 2.1rem; font-weight: 600; line-height: 1.2; margin-bottom: 10px; }
.hero-sub { font-size: 1.02rem; opacity: 0.85; max-width: 62ch; line-height: 1.55; }
.hero-chips { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 8px; }
.hero-chips span { font-size: 0.8rem; padding: 4px 11px; border-radius: 999px; border: 1px solid rgba(127,127,127,0.32); }
.mini-stat-label { font-size: 0.95rem; opacity: 0.85; margin-bottom: 6px; }
div[data-testid="stVerticalBlockBorderWrapper"]:has(.mini-stat-card) { padding: 16px 18px 26px !important; }
.mini-stat-value { font-size: 1.15rem; font-weight: 600; line-height: 1.3; word-break: break-word; overflow-wrap: break-word; }
.home-footer { text-align: center; opacity: 0.65; font-size: 0.8rem; padding: 6px 0 2px; }

/* tampilan HP */
@media (max-width: 768px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    div[data-testid="stElementContainer"]:has(.logo-bar), .element-container:has(.logo-bar) { right: 1rem; left: 1rem; }
    .logo-bar { justify-content: flex-end; gap: 10px; }
    .logo-bar img { height: 24px; }
    [data-testid="stTabs"] > [data-baseweb="tab-list"] { margin-top: 52px; }
    [data-testid="stTabs"] [data-testid="stTabs"] > [data-baseweb="tab-list"] { margin-top: 0; }
    .hero { padding: 20px 18px 18px; }
    .hero-title { font-size: 1.5rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------
# Koordinat
# ---------------------------------------------------------------


def parse_koordinat(value, tipe):
    """Ubah koordinat mentah (DMS atau desimal, dengan/tanpa N/S/E/W)
    jadi desimal. tipe = "lat" atau "lon". Kalau gagal atau di luar
    rentang Bogor, hasilnya NaN."""
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if s == "" or s.lower() == "nan":
        return np.nan

    s = s.replace("\u201c", '"').replace("\u201d", '"').replace("''", '"')

    # huruf mata angin di ujung
    hemisphere = None
    m_hem = re.search(r"([NSEWnsew])\s*$", s)
    if m_hem:
        hemisphere = m_hem.group(1).upper()
        s = s[: m_hem.start()].strip()
    valid_hem = {"N", "S"} if tipe == "lat" else {"E", "W"}
    if hemisphere not in valid_hem:
        hemisphere = None

    negative = s.startswith("-")
    s_clean = s.lstrip("-").strip()

    decimal = None
    # derajat-menit-detik, mis. 106°53'14,634
    dms = re.match(r"^(\d{1,3})[°ºo⁰\s]+(\d{1,2})['\u2019\s]+([\d.,]+)", s_clean)
    if dms:
        deg = float(dms.group(1))
        minute = float(dms.group(2))
        sec_str = dms.group(3).replace(",", ".").strip(".")
        try:
            sec = float(sec_str) if sec_str else 0.0
        except ValueError:
            sec = 0.0
        if minute < 60 and sec < 60:
            decimal = deg + minute / 60 + sec / 3600
    if decimal is None:
        # desimal biasa
        dd = re.match(r"^(\d{1,3}[.,]\d+)", s_clean)
        if dd:
            decimal = float(dd.group(1).replace(",", "."))
        else:
            try:
                decimal = float(s_clean.replace(",", "."))
            except ValueError:
                return np.nan

    if hemisphere in ("S", "W"):
        decimal = -abs(decimal)
    elif hemisphere in ("N", "E"):
        decimal = abs(decimal)
    elif negative:
        decimal = -abs(decimal)
    else:
        decimal = -abs(decimal) if tipe == "lat" else abs(decimal)

    if tipe == "lat" and not (-8 <= decimal <= -5):
        return np.nan
    if tipe == "lon" and not (105 <= decimal <= 108):
        return np.nan
    return round(decimal, 6)


def isi_koordinat_otomatis(df_events, rng_seed=1):
    """Isi lat/lon yang kosong dengan titik tengah kecamatan + sedikit
    offset acak supaya titiknya tidak numpuk."""
    df_events = df_events.copy()
    rng = np.random.default_rng(rng_seed)
    lookup = {k["n"].lower(): (k["lat"], k["lon"]) for k in KECAMATAN_BOGOR}

    for kol in ["lat", "lon"]:
        if kol not in df_events.columns:
            df_events[kol] = np.nan

    tidak_cocok = set()
    need_fill = df_events["lat"].isna() | df_events["lon"].isna()
    for i in df_events.index[need_fill]:
        key = str(df_events.at[i, "kecamatan"]).strip().lower()
        if key in lookup:
            base_lat, base_lon = lookup[key]
            df_events.at[i, "lat"] = base_lat + rng.uniform(-0.03, 0.03)
            df_events.at[i, "lon"] = base_lon + rng.uniform(-0.03, 0.03)
        else:
            tidak_cocok.add(df_events.at[i, "kecamatan"])

    if tidak_cocok:
        st.sidebar.warning(
            "Nama kecamatan ini tidak cocok dengan daftar 40 kecamatan, jadi tidak tampil di peta: "
            + ", ".join(sorted(str(x) for x in tidak_cocok))
        )
    return df_events


# ---------------------------------------------------------------
# Data simulasi
# ---------------------------------------------------------------


def klasifikasi_curah_hujan(mm_per_hari):
    """Kategori hujan harian menurut BMKG."""
    if pd.isna(mm_per_hari):
        return "Tidak Diketahui"
    if mm_per_hari < 5:
        return "Tidak Hujan/Berawan"
    elif mm_per_hari < 20:
        return "Ringan"
    elif mm_per_hari < 50:
        return "Sedang"
    elif mm_per_hari < 100:
        return "Lebat"
    return "Sangat Lebat"


@st.cache_data
def generate_dummy_data(n_rows=220, seed=42):
    rng = np.random.default_rng(seed)
    types = list(TYPE_COLUMN_MAP.values())
    rows = []
    for _ in range(n_rows):
        jenis = rng.choice(types)
        kec = KECAMATAN_BOGOR[rng.integers(0, len(KECAMATAN_BOGOR))]
        bulan = rng.integers(1, 10)
        hari = rng.integers(1, 28)
        tahun = rng.choice([2024, 2025, 2026], p=[0.25, 0.35, 0.40])
        keparahan = round(float(rng.uniform(1.0, 5.0)), 1)
        rows.append(
            {
                "tanggal": pd.Timestamp(year=int(tahun), month=int(bulan), day=int(hari)),
                "jenis_bencana": jenis,
                "kecamatan": kec["n"],
                "lat": kec["lat"] + rng.uniform(-0.03, 0.03),
                "lon": kec["lon"] + rng.uniform(-0.03, 0.03),
                "meninggal": int(rng.poisson(keparahan * 0.3)),
                "mengungsi": int(rng.poisson(keparahan * 80)),
                "rumah_terdampak": int(rng.poisson(keparahan * 15)),
                "keparahan": keparahan,
                "status": rng.choice(STATUS_OPTIONS, p=[0.40, 0.35, 0.15, 0.10]),
            }
        )
    return pd.DataFrame(rows).sort_values("tanggal", ascending=False).reset_index(drop=True)


@st.cache_data
def generate_meteo_data(seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for kec in KECAMATAN_BOGOR:
        southness = max(0.0, (-6.35 - kec["lat"]))
        curah = max(0.0, float(rng.normal(12 + southness * 55, 12)))
        rows.append(
            {
                "kecamatan": kec["n"],
                "lat": kec["lat"],
                "lon": kec["lon"],
                "curah_hujan_mm_hari": round(curah, 1),
                "kategori_intensitas": klasifikasi_curah_hujan(curah),
                "suhu_c": round(float(rng.normal(26 - southness * 4, 1.2)), 1),
                "kelembaban_persen": round(float(np.clip(rng.normal(80, 6), 55, 99)), 0),
                "kecepatan_angin_kmh": round(float(np.clip(rng.normal(14, 5), 2, 40)), 1),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------
# Data meteorologi
# ---------------------------------------------------------------


def _norm_nama(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


_KEC_LOOKUP = {_norm_nama(k["n"]): k["n"] for k in KECAMATAN_BOGOR}


def cari_kecamatan_dari_nama_file(filename):
    """Tebak kecamatan dari nama file, mis. data_ch_Cibinong_2026.csv -> Cibinong."""
    base = re.sub(r"\.csv$", "", filename, flags=re.IGNORECASE)
    norm = _norm_nama(base)
    kandidat = [asli for key, asli in _KEC_LOOKUP.items() if key and key in norm]
    if not kandidat:
        return None
    # kalau ada beberapa yang cocok, ambil nama terpanjang
    return max(kandidat, key=len)


# variasi nama kolom yang diterima
ALIAS_KOLOM_METEO = {
    "kecamatan": {"kecamatan", "kec", "nama_kecamatan"},
    "curah_hujan_mm_hari": {
        "curah_hujan_mm_hari", "curah_hujan", "curah_hujan_mm", "curah_hujan_mmhari",
        "curahhujan", "hujan", "rainfall", "precipitation", "ch", "rr", "curah",
    },
    "suhu_c": {"suhu_c", "suhu", "temperature", "temp", "suhu_celcius", "suhu_udara"},
    "kelembaban_persen": {"kelembaban_persen", "kelembaban", "kelembapan", "humidity", "rh"},
    "kecepatan_angin_kmh": {
        "kecepatan_angin_kmh", "kecepatan_angin", "angin", "wind_speed", "windspeed",
        "kecepatan_angin_km_jam", "ws",
    },
}


def _norm_kolom(nama):
    s = str(nama).strip().lower()
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _petakan_kolom_meteo(df_csv):
    kolom_norm = {_norm_kolom(c): c for c in df_csv.columns}
    ganti = {}
    for nama_baku, alias_set in ALIAS_KOLOM_METEO.items():
        for alias in alias_set:
            if alias in kolom_norm:
                ganti[kolom_norm[alias]] = nama_baku
                break
    return df_csv.rename(columns=ganti)


def _baca_csv_fleksibel(uploaded_file):
    """Baca CSV dengan pemisah otomatis (koma/titik koma/tab) dan buang BOM."""
    uploaded_file.seek(0)
    raw = uploaded_file.read()
    if isinstance(raw, bytes):
        text = raw.decode("utf-8-sig", errors="replace")
    else:
        text = raw.lstrip("\ufeff")
    uploaded_file.seek(0)
    return pd.read_csv(StringIO(text), sep=None, engine="python")


def _parse_angka(value):
    """Parse angka format Indonesia (9,2963) maupun internasional (9.2963)."""
    if pd.isna(value):
        return np.nan
    s = str(value).strip()
    if s == "":
        return np.nan
    try:
        return float(s)
    except ValueError:
        pass
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return np.nan


def _perlu_pilih_manual_kecamatan(uploaded_file):
    """True kalau kecamatan tidak bisa ditebak dari nama file maupun kolom."""
    if cari_kecamatan_dari_nama_file(uploaded_file.name) is not None:
        return False
    try:
        preview = _baca_csv_fleksibel(uploaded_file)
        preview.columns = [str(c).strip() for c in preview.columns]
        preview = _petakan_kolom_meteo(preview)
        return "kecamatan" not in preview.columns
    except Exception:
        return True
    finally:
        uploaded_file.seek(0)


def _baca_satu_file_meteo(uploaded_file, kecamatan_override=None):
    """Baca satu file meteorologi, rata-ratakan per kecamatan.
    Return (df, None) kalau berhasil, atau (None, pesan_error)."""
    try:
        df_csv = _baca_csv_fleksibel(uploaded_file)
    except Exception:
        return None, f"File `{uploaded_file.name}` gagal dibaca sebagai CSV."

    df_csv.columns = [str(c).strip() for c in df_csv.columns]
    df_csv = _petakan_kolom_meteo(df_csv)

    if "curah_hujan_mm_hari" not in df_csv.columns:
        return None, (
            f"File `{uploaded_file.name}` dilewati karena tidak ada kolom curah hujan "
            "(coba beri nama kolom \"curah_hujan\", \"ch\", atau \"rr\")."
        )

    for kol in ["suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]:
        if kol not in df_csv.columns:
            df_csv[kol] = np.nan
    for kol in ["curah_hujan_mm_hari", "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]:
        df_csv[kol] = df_csv[kol].apply(_parse_angka)

    if "kecamatan" in df_csv.columns and df_csv["kecamatan"].notna().any():
        df_csv["kecamatan"] = df_csv["kecamatan"].astype(str).str.strip()
        df_csv["kecamatan"] = df_csv["kecamatan"].apply(lambda v: _KEC_LOOKUP.get(_norm_nama(v), v))
    elif kecamatan_override:
        df_csv["kecamatan"] = kecamatan_override
    else:
        return None, (
            f"File `{uploaded_file.name}` dilewati karena tidak ada kolom kecamatan "
            "dan nama kecamatan tidak terbaca dari nama file."
        )

    df_csv = df_csv.dropna(subset=["curah_hujan_mm_hari", "kecamatan"])
    if df_csv.empty:
        return None, f"File `{uploaded_file.name}` dilewati karena tidak ada baris curah hujan yang valid."

    agg = df_csv.groupby("kecamatan").agg(
        curah_hujan_mm_hari=("curah_hujan_mm_hari", "mean"),
        suhu_c=("suhu_c", "mean"),
        kelembaban_persen=("kelembaban_persen", "mean"),
        kecepatan_angin_kmh=("kecepatan_angin_kmh", "mean"),
    ).reset_index()
    return agg, None


def load_meteo_data_multi(uploaded_files, kecamatan_override_map):
    """Gabungkan semua file meteorologi. Return (df, daftar_pesan)."""
    semua_hasil = []
    pesan = []
    for f in uploaded_files:
        override = kecamatan_override_map.get(f.name) or cari_kecamatan_dari_nama_file(f.name)
        hasil, err = _baca_satu_file_meteo(f, kecamatan_override=override)
        if err:
            pesan.append(err)
            continue
        semua_hasil.append(hasil)

    kolom = ["kecamatan", "lat", "lon", "curah_hujan_mm_hari", "kategori_intensitas",
             "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]
    if not semua_hasil:
        return pd.DataFrame(columns=kolom), pesan

    gabungan = pd.concat(semua_hasil, ignore_index=True)

    duplikat = sorted(gabungan["kecamatan"][gabungan["kecamatan"].duplicated()].unique())
    if duplikat:
        pesan.append(
            "Kecamatan ini ada di lebih dari satu file meteorologi, nilainya dirata-ratakan: "
            + ", ".join(duplikat)
        )
    gabungan = gabungan.groupby("kecamatan", as_index=False).mean(numeric_only=True)

    dikenal = set(_KEC_LOOKUP.values())
    tidak_dikenal = sorted(set(gabungan["kecamatan"]) - dikenal)
    if tidak_dikenal:
        pesan.append(
            "Kecamatan ini tidak cocok dengan daftar 40 kecamatan dan diabaikan: "
            + ", ".join(tidak_dikenal)
        )
        gabungan = gabungan[gabungan["kecamatan"].isin(dikenal)]

    if gabungan.empty:
        return pd.DataFrame(columns=kolom), pesan

    koordinat = {k["n"]: (k["lat"], k["lon"]) for k in KECAMATAN_BOGOR}
    gabungan["lat"] = gabungan["kecamatan"].map(lambda k: koordinat[k][0])
    gabungan["lon"] = gabungan["kecamatan"].map(lambda k: koordinat[k][1])
    gabungan["kategori_intensitas"] = gabungan["curah_hujan_mm_hari"].apply(klasifikasi_curah_hujan)
    return gabungan[kolom].reset_index(drop=True), pesan


def compute_risk_index(df_events, df_meteo, daftar_kecamatan):
    """Indeks risiko sederhana 0-100 per kecamatan:
    45% jumlah kejadian + 30% rata-rata keparahan + 25% curah hujan
    (masing-masing dinormalisasi min-max). Bukan IRBI resmi."""
    agg = (
        df_events.groupby("kecamatan")
        .agg(jumlah_kejadian=("kecamatan", "size"), rata_keparahan=("keparahan", "mean"))
        .reset_index()
    )
    out = pd.DataFrame({"kecamatan": list(daftar_kecamatan)})
    out = out.merge(agg, on="kecamatan", how="left").fillna({"jumlah_kejadian": 0, "rata_keparahan": 0})
    out = out.merge(df_meteo[["kecamatan", "curah_hujan_mm_hari"]], on="kecamatan", how="left")

    def norm(s):
        selisih = s.max() - s.min()
        return (s - s.min()) / selisih if selisih and selisih > 0 else s * 0

    out["indeks_risiko"] = (
        0.45 * norm(out["jumlah_kejadian"])
        + 0.30 * norm(out["rata_keparahan"])
        + 0.25 * norm(out["curah_hujan_mm_hari"])
    ) * 100
    out["indeks_risiko"] = out["indeks_risiko"].round(1)
    out["kategori_risiko"] = pd.cut(
        out["indeks_risiko"], bins=[-1, 33, 66, 101], labels=["Rendah", "Sedang", "Tinggi"]
    )
    return out


# ---------------------------------------------------------------
# Data kejadian bencana
# ---------------------------------------------------------------


def _cari_baris_header(uploaded_file):
    """Cari baris header di 5 baris pertama (ada KECAMATAN dan BANJIR)."""
    uploaded_file.seek(0)
    preview = pd.read_csv(uploaded_file, header=None, nrows=5, dtype=str)
    for i in range(len(preview)):
        nilai = set(str(v).strip().upper() for v in preview.iloc[i].tolist())
        if "KECAMATAN" in nilai and "BANJIR" in nilai:
            return i
    return None


def _parse_format_bpbd(uploaded_file):
    """Parse CSV format laporan BPBD. Return None kalau bukan format ini."""
    header_idx = _cari_baris_header(uploaded_file)
    if header_idx is None:
        return None

    uploaded_file.seek(0)
    df_raw = pd.read_csv(uploaded_file, skiprows=header_idx, header=0, low_memory=False)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    col_lookup = {c.upper(): c for c in df_raw.columns}

    if "KECAMATAN" not in col_lookup or "TANGGAL KEJADIAN" not in col_lookup:
        return None

    def col_num(name):
        key = name.strip().upper()
        if key in col_lookup:
            return pd.to_numeric(df_raw[col_lookup[key]], errors="coerce").fillna(0)
        return pd.Series(0, index=df_raw.index)

    # 8 kolom jenis bencana -> 1 kolom
    ind_df = pd.DataFrame(index=df_raw.index)
    for raw_key, display in TYPE_COLUMN_MAP.items():
        if raw_key in col_lookup:
            ind_df[display] = pd.to_numeric(df_raw[col_lookup[raw_key]], errors="coerce").fillna(0)
    if ind_df.shape[1] == 0:
        return None
    ada_jenis = ind_df.sum(axis=1) > 0
    jenis = ind_df.idxmax(axis=1).where(ada_jenis, "Tidak Diketahui")

    # tanggal (M/D/YYYY, kalau gagal pakai parser umum)
    tanggal_col = col_lookup["TANGGAL KEJADIAN"]
    tanggal = pd.to_datetime(df_raw[tanggal_col], format="%m/%d/%Y", errors="coerce")
    gagal = tanggal.isna() & df_raw[tanggal_col].notna()
    if gagal.any():
        tanggal.loc[gagal] = pd.to_datetime(df_raw.loc[gagal, tanggal_col], errors="coerce")

    # koordinat
    lon_col = col_lookup.get("LONGITUDE")
    lat_col = col_lookup.get("LATITUDE")
    lon_parsed = df_raw[lon_col].apply(lambda v: parse_koordinat(v, "lon")) if lon_col else pd.Series(np.nan, index=df_raw.index)
    lat_parsed = df_raw[lat_col].apply(lambda v: parse_koordinat(v, "lat")) if lat_col else pd.Series(np.nan, index=df_raw.index)
    tidak_valid = lon_parsed.isna() | lat_parsed.isna()
    lon_parsed[tidak_valid] = np.nan
    lat_parsed[tidak_valid] = np.nan

    # dampak
    meninggal = col_num("MENINGGAL DUNIA (JIWA)")
    luka_berat = col_num("LUKA BERAT (JIWA)")
    luka_sedang = col_num("LUKA SEDANG (JIWA)")
    luka_ringan = col_num("LUKA RINGAN (JIWA)")
    mengungsi = col_num("MENGUNGSI (JIWA)")
    rumah_ringan = col_num("RUMAH RUSAK RINGAN")
    rumah_sedang = col_num("RUMAH RUSAK SEDANG")
    rumah_berat = col_num("RUMAH RUSAK BERAT")
    rumah_terancam = col_num("RUMAH TERANCAM")
    rumah_terendam = col_num("RUMAH TERENDAM")
    rumah_terdampak = rumah_ringan + rumah_sedang + rumah_berat + rumah_terancam + rumah_terendam

    # skor dampak -> keparahan 1-5 (skala log)
    dampak_score = (
        meninggal * 5 + luka_berat * 3 + luka_sedang * 2 + luka_ringan * 1
        + rumah_berat * 2 + rumah_sedang * 1 + rumah_ringan * 0.5
        + rumah_terendam * 0.5 + rumah_terancam * 0.3
        + mengungsi * 0.02
    )
    max_score = dampak_score.max()
    if max_score > 0:
        keparahan = (1 + 4 * np.log1p(dampak_score) / np.log1p(max_score)).clip(1, 5)
    else:
        keparahan = pd.Series(1.0, index=df_raw.index)

    # status darurat
    status_key = "STATUS KEADAAN DARURAT BENCANA"
    if status_key in col_lookup:
        status = df_raw[col_lookup[status_key]].fillna("Tidak Diketahui").astype(str).str.strip().str.upper()
        status = status.replace({"TANGGAP DARUAT": "TANGGAP DARURAT", "": "TIDAK DIKETAHUI"})
        status = status.str.title()
    else:
        status = pd.Series("Tidak Diketahui", index=df_raw.index)

    hasil = pd.DataFrame(
        {
            "tanggal": tanggal,
            "jenis_bencana": jenis,
            "kecamatan": df_raw[col_lookup["KECAMATAN"]].astype(str).str.strip(),
            "lat": lat_parsed,
            "lon": lon_parsed,
            "meninggal": meninggal.astype(int),
            "mengungsi": mengungsi.astype(int),
            "rumah_terdampak": rumah_terdampak.astype(int),
            "keparahan": keparahan.round(1),
            "status": status,
            "_dampak_score": dampak_score,
        }
    )
    hasil = hasil.dropna(subset=["tanggal", "kecamatan"])
    return isi_koordinat_otomatis(hasil)


def _parse_format_sederhana(uploaded_file):
    """Format sederhana: kolom tanggal, jenis_bencana, kecamatan wajib ada."""
    uploaded_file.seek(0)
    try:
        df_csv = pd.read_csv(uploaded_file, parse_dates=["tanggal"])
    except (ValueError, KeyError):
        return None
    if not {"tanggal", "jenis_bencana", "kecamatan"}.issubset(df_csv.columns):
        return None

    df_csv = isi_koordinat_otomatis(df_csv)
    for kol, default in [
        ("meninggal", 0), ("mengungsi", 0), ("rumah_terdampak", 0),
        ("keparahan", 2.5), ("status", "Tidak Diketahui"),
    ]:
        if kol not in df_csv.columns:
            df_csv[kol] = default
    return df_csv


def load_data(uploaded_files):
    """Muat data kejadian bencana. Tiap file dicoba sebagai format BPBD,
    lalu format sederhana. Kalau tidak ada yang cocok, pakai data simulasi."""
    if not uploaded_files:
        return generate_dummy_data()

    bagian = []
    dilewati = []
    for f in uploaded_files:
        hasil = None
        try:
            hasil = _parse_format_bpbd(f)
            if hasil is None or len(hasil) == 0:
                hasil = _parse_format_sederhana(f)
        except Exception:
            hasil = None
        if hasil is None or len(hasil) == 0:
            dilewati.append(f.name)
            continue
        bagian.append(hasil)

    if dilewati:
        st.sidebar.warning("File kejadian bencana ini formatnya tidak dikenali dan dilewati: " + ", ".join(dilewati))
    if not bagian:
        st.sidebar.error(
            "Tidak ada file kejadian bencana yang formatnya dikenali. Pakai format laporan BPBD "
            "atau kolom tanggal, jenis_bencana, kecamatan. Sementara ditampilkan data simulasi."
        )
        return generate_dummy_data()

    gabungan = pd.concat(bagian, ignore_index=True)

    # hitung ulang keparahan pakai skala gabungan semua file
    if "_dampak_score" in gabungan.columns:
        skor = gabungan["_dampak_score"]
        ada = skor.notna()
        if ada.any():
            maks = skor[ada].max()
            if maks > 0:
                gabungan.loc[ada, "keparahan"] = (
                    (1 + 4 * np.log1p(skor[ada]) / np.log1p(maks)).clip(1, 5).round(1)
                )
            else:
                gabungan.loc[ada, "keparahan"] = 1.0
        gabungan = gabungan.drop(columns=["_dampak_score"])

    return gabungan.sort_values("tanggal", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------

BANTUAN_BENCANA = (
    "Bisa format laporan BPBD Kabupaten Bogor atau format sederhana (kolom tanggal, "
    "jenis_bencana, kecamatan). Boleh lebih dari satu file. Kosongkan untuk memakai data simulasi."
)
BANTUAN_METEO = (
    "Satu file bisa berisi satu kecamatan (nama dari nama file, mis. cibinong.csv) atau "
    "banyak kecamatan (butuh kolom kecamatan). Nama kolom curah hujan fleksibel "
    "(\"curah hujan\", \"ch\", \"rr\", dst). Kecamatan yang tidak ada di data meteorologi "
    "tidak ditampilkan."
)


def widget_unggah_csv(kunci, label_mode, label_file, label_folder, label_cadangan, bantuan):
    """Widget unggah CSV: pilih file (bisa banyak) atau pilih folder."""
    mode = st.radio(label_mode, ["Pilih file CSV", "Pilih folder"], horizontal=True, key=f"mode_unggah_{kunci}")
    if mode == "Pilih folder":
        try:
            files = st.file_uploader(
                label_folder, type=["csv"], accept_multiple_files="directory",
                key=f"{kunci}_folder",
                help="Pilih satu folder, semua CSV di dalamnya ikut terunggah. " + bantuan,
            )
        except Exception:
            st.warning("Versi Streamlit ini belum mendukung unggah folder. Pilih beberapa file CSV saja.")
            files = st.file_uploader(
                label_cadangan, type=["csv"], accept_multiple_files=True,
                key=f"{kunci}_file_cadangan", help=bantuan,
            )
    else:
        files = st.file_uploader(
            label_file, type=["csv"], accept_multiple_files=True,
            key=f"{kunci}_file", help=bantuan,
        )
    return files or []


with st.sidebar:
    st.markdown("### Pengaturan Data")

    uploaded_bencana_files = widget_unggah_csv(
        "bencana",
        label_mode="Cara unggah data kejadian bencana",
        label_file="Unggah CSV kejadian bencana (boleh lebih dari satu file)",
        label_folder="Unggah folder berisi CSV kejadian bencana",
        label_cadangan="Unggah CSV kejadian bencana (boleh lebih dari satu file)",
        bantuan=BANTUAN_BENCANA,
    )

    st.markdown("---")

    uploaded_meteo_files = widget_unggah_csv(
        "meteo",
        label_mode="Cara unggah data meteorologi",
        label_file="Unggah CSV meteorologi (satu per kecamatan atau gabungan)",
        label_folder="Unggah folder berisi CSV meteorologi",
        label_cadangan="Unggah CSV meteorologi (boleh lebih dari satu file)",
        bantuan=BANTUAN_METEO,
    )

    ada_data_bencana = len(uploaded_bencana_files) > 0
    ada_data_meteo = len(uploaded_meteo_files) > 0

    # file meteorologi yang kecamatannya tidak terbaca: pilih manual
    kecamatan_override_map = {}
    if uploaded_meteo_files:
        file_perlu_override = [f for f in uploaded_meteo_files if _perlu_pilih_manual_kecamatan(f)]
        if file_perlu_override:
            st.caption("Kecamatan tidak terbaca otomatis untuk file berikut, pilih manual:")
            for f in file_perlu_override:
                kecamatan_override_map[f.name] = st.selectbox(
                    f"Kecamatan untuk `{f.name}`",
                    [k["n"] for k in KECAMATAN_BOGOR],
                    key=f"override_kec_{f.name}",
                )

    st.markdown("---")
    st.markdown("### Filter")

    df_all = load_data(uploaded_bencana_files)

    if uploaded_meteo_files:
        df_meteo_real, pesan_meteo = load_meteo_data_multi(uploaded_meteo_files, kecamatan_override_map)
        for p in pesan_meteo:
            st.warning(p)
        if df_meteo_real.empty:
            st.error("Tidak ada data meteorologi valid dari file yang diunggah. Dipakai data simulasi untuk 40 kecamatan.")
            df_meteo = generate_meteo_data()
            meteo_dari_file = False
        else:
            df_meteo = df_meteo_real
            meteo_dari_file = True
    else:
        df_meteo = generate_meteo_data()
        meteo_dari_file = False

    # hanya kecamatan yang punya data bencana DAN meteorologi
    kec_bencana = set(df_all["kecamatan"].unique())
    kec_meteo = set(df_meteo["kecamatan"].unique())
    kecamatan_aktif = sorted(kec_bencana & kec_meteo)

    if meteo_dari_file:
        hanya_bencana = sorted(kec_bencana - kec_meteo)
        hanya_meteo = sorted(kec_meteo - kec_bencana)
        if hanya_bencana:
            st.info(
                f"{len(hanya_bencana)} kecamatan punya data bencana tapi belum ada data meteorologi, "
                "jadi tidak ditampilkan: " + ", ".join(hanya_bencana)
            )
        if hanya_meteo:
            st.info(
                f"{len(hanya_meteo)} kecamatan punya data meteorologi tapi tidak ada data bencana, "
                "jadi tidak ditampilkan: " + ", ".join(hanya_meteo)
            )
        st.caption(f"✅ {len(kecamatan_aktif)} kecamatan aktif (data bencana dan meteorologi lengkap).")

    df_all = df_all[df_all["kecamatan"].isin(kecamatan_aktif)].reset_index(drop=True)
    df_meteo = df_meteo[df_meteo["kecamatan"].isin(kecamatan_aktif)].reset_index(drop=True)

    tahun_opsi = sorted(df_all["tanggal"].dt.year.unique(), reverse=True) if not df_all.empty else []
    tahun_pilih = st.multiselect("Tahun", tahun_opsi, default=tahun_opsi)

    # opsi bulan menyesuaikan tahun yang dipilih
    df_untuk_bulan = df_all[df_all["tanggal"].dt.year.isin(tahun_pilih)] if tahun_pilih else df_all
    bulan_tersedia = sorted(df_untuk_bulan["tanggal"].dt.month.unique())
    bulan_pilih_nama = st.multiselect(
        "Bulan", [NAMA_BULAN[b] for b in bulan_tersedia], default=[], placeholder="Semua bulan"
    )
    nama_ke_angka = {v: k for k, v in NAMA_BULAN.items()}
    bulan_pilih_angka = [nama_ke_angka[b] for b in bulan_pilih_nama]

    jenis_opsi = sorted(df_all["jenis_bencana"].unique())
    jenis_pilih = st.multiselect("Jenis bencana", jenis_opsi, default=jenis_opsi)

    kecamatan_opsi = sorted(df_all["kecamatan"].unique())
    kecamatan_pilih = st.multiselect("Kecamatan", kecamatan_opsi, default=[], placeholder="Semua kecamatan")

    st.markdown("---")
    st.caption("Prototipe Departemen Geofisika dan Meteorologi, IPB University. Cakupan: Kabupaten Bogor.")

if not kecamatan_aktif:
    st.error(
        "Tidak ada kecamatan yang punya data bencana dan data meteorologi sekaligus. "
        "Cek nama kecamatan di kedua file, atau kosongkan salah satu untuk memakai data simulasi."
    )
    st.stop()

# terapkan filter
df = df_all[df_all["tanggal"].dt.year.isin(tahun_pilih) & df_all["jenis_bencana"].isin(jenis_pilih)]
if bulan_pilih_angka:
    df = df[df["tanggal"].dt.month.isin(bulan_pilih_angka)]
if kecamatan_pilih:
    df = df[df["kecamatan"].isin(kecamatan_pilih)]

df_risk = compute_risk_index(df, df_meteo, kecamatan_aktif)

# ---------------------------------------------------------------
# Logo, halaman Home, peta analisis
# ---------------------------------------------------------------


def html_logo_bar():
    """Logo IPB, BPBD, BMKG dari folder logos/ (png/jpg). Yang tidak ada dilewati."""
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}
    img_tags = []
    for label, nama_file in [("IPB University", "logo_ipb"), ("BPBD Kab. Bogor", "logo_bpbd"), ("BMKG", "logo_bmkg")]:
        for ext in ["png", "jpg", "jpeg"]:
            path = os.path.join(LOGO_DIR, f"{nama_file}.{ext}")
            if os.path.exists(path):
                with open(path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                img_tags.append(f'<img src="data:{mime[ext]};base64,{b64}" alt="{label}" title="{label}">')
                break
    if not img_tags:
        return ""
    return f'<div class="logo-bar">{"".join(img_tags)}</div>'


_logo_html = html_logo_bar()
if _logo_html:
    st.markdown(_logo_html, unsafe_allow_html=True)


def halaman_home(df_data, kecamatan_aktif, ada_data_bencana, ada_data_meteo):
    bulan_singkat = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

    st.markdown(
        f"""
<div class="hero">
  <div class="hero-kicker">Departemen Geofisika dan Meteorologi · IPB University</div>
  <div class="hero-title">Dashboard Pemantauan Bencana<br>Kabupaten Bogor</div>
  <div class="hero-sub">Menghubungkan data kejadian bencana dengan kondisi meteorologi
  per kecamatan, untuk melihat di mana bencana sering terjadi dan kaitannya dengan cuaca.</div>
  <div class="hero-chips">
    <span>{len(KECAMATAN_BOGOR)} kecamatan</span>
    <span>{len(TYPE_COLUMN_MAP)} jenis bencana</span>
    <span>Peta analisis 2026</span>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption("Unggah data dan atur filter lewat sidebar, lalu buka tab **Dashboard Utama** atau **Peta Analisis 2026**.")

    st.markdown("### Latar belakang")
    kiri, kanan = st.columns([1.4, 1])
    with kiri:
        st.markdown(
            """
Kabupaten Bogor terdiri dari 40 kecamatan, dari dataran rendah di utara sampai
pegunungan di selatan, dengan curah hujan yang tinggi. Wilayah ini rentan terhadap
bencana hidrometeorologi seperti banjir, tanah longsor, angin kencang, dan kekeringan.

Curah hujan, kelembapan, suhu, dan kecepatan angin bisa memicu atau memperparah
kejadian bencana. Memahami kaitannya penting untuk mengenali potensi bencana lebih
awal dan merencanakan mitigasi.

Dashboard ini dibuat oleh mahasiswa Departemen Geofisika dan Meteorologi IPB University
sebagai prototipe alat bantu untuk memantau dan menganalisis kejadian bencana di
Kabupaten Bogor berbasis data.
"""
        )
    with kanan:
        with st.container(border=True):
            st.markdown("**Tujuan**")
            st.markdown(
                "- Menampilkan sebaran kejadian bencana per jenis, waktu, dan kecamatan.\n"
                "- Melihat kaitan curah hujan dengan bencana hidrometeorologi.\n"
                "- Membandingkan indeks risiko sederhana antar-kecamatan.\n"
                "- Menyediakan peta hasil analisis bencana 2026 per jenis bencana."
            )

    st.markdown("### Yang bisa dilihat di dashboard")
    fitur = [
        ("Sebaran kejadian", "Peta titik kejadian per jenis bencana, ukuran titik sesuai keparahan."),
        ("Tren & komposisi", "Jumlah kejadian per bulan, komposisi jenis bencana, dan kecamatan terbanyak."),
        ("Korelasi meteorologi", "Hubungan curah hujan dengan bencana hidrometeorologi, dengan garis regresi dan R²."),
        ("Peta analisis 2026", "Peta hasil analisis yang disiapkan terpisah, dipilih per jenis bencana."),
    ]
    for kolom, (judul, isi) in zip(st.columns(len(fitur)), fitur):
        with kolom:
            with st.container(border=True):
                st.markdown(f"**{judul}**")
                st.caption(isi)

    st.markdown("### Cara menggunakan")
    st.markdown(
        """
1. **Siapkan data.** Di sidebar, unggah CSV kejadian bencana (format BPBD) dan CSV meteorologi,
   bisa satu file, beberapa file, atau satu folder. Tanpa unggahan, dashboard memakai data simulasi.
2. **Atur filter.** Pilih tahun, bulan, jenis bencana, dan kecamatan.
3. **Baca hasilnya.** Buka tab **Dashboard Utama**.
4. **Lihat peta analisis.** Buka tab **Peta Analisis 2026**, lalu pilih jenis bencananya.
"""
    )

    st.markdown("### Sekilas data")
    if ada_data_bencana:
        st.caption("Ringkasan seluruh periode dari file yang diunggah (hanya kecamatan dengan data lengkap).")
    else:
        st.caption("Ringkasan data simulasi. Unggah CSV kejadian bencana di sidebar untuk melihat data sebenarnya.")
    if len(df_data) > 0:
        tgl_min, tgl_max = df_data["tanggal"].min(), df_data["tanggal"].max()
        periode = f"{bulan_singkat[tgl_min.month - 1]} {tgl_min.year} – {bulan_singkat[tgl_max.month - 1]} {tgl_max.year}"
        stat_items = [
            ("Total kejadian", f"{len(df_data):,}".replace(",", ".")),
            ("Jenis terbanyak", df_data["jenis_bencana"].value_counts().idxmax()),
            ("Kecamatan terbanyak", df_data["kecamatan"].value_counts().idxmax()),
            ("Periode data", periode),
        ]
        for kolom, (label, value) in zip(st.columns(4), stat_items):
            with kolom:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="mini-stat-card"><div class="mini-stat-label">{label}</div>'
                        f'<div class="mini-stat-value">{value}</div></div>',
                        unsafe_allow_html=True,
                    )

    st.markdown("### Sumber data dan metode")
    m1, m2 = st.columns(2)
    with m1:
        with st.container(border=True):
            st.markdown("**Data yang dipakai**")
            st.markdown(
                "- **Kejadian bencana:** laporan BPBD Kabupaten Bogor (jenis, waktu, lokasi, korban, rumah terdampak).\n"
                "- **Meteorologi:** curah hujan, suhu, kelembapan, dan kecepatan angin per kecamatan "
                "(diunggah pengguna, kalau tidak ada dipakai data simulasi).\n"
                "- **Peta analisis 2026:** hasil analisis terpisah per jenis bencana."
            )
    with m2:
        with st.container(border=True):
            st.markdown("**Cara perhitungan**")
            st.markdown(
                "- **Intensitas hujan:** klasifikasi harian BMKG (ringan 5–20, sedang 20–50, "
                "lebat 50–100, sangat lebat di atas 100 mm/hari).\n"
                "- **Keparahan (1–5):** proksi dari korban jiwa, luka, rumah rusak, rumah terdampak, dan pengungsi.\n"
                "- **Indeks risiko (0–100):** jumlah kejadian (45%), rata-rata keparahan (30%), curah hujan (25%)."
            )

    st.markdown("### Pertanyaan yang sering diajukan")
    with st.expander("Apa arti ukuran titik di peta sebaran?"):
        st.write(
            "Ukuran titik menunjukkan indeks keparahan (proksi dampak pada manusia dan rumah), "
            "bukan luas area bencana."
        )
    with st.expander("Apakah indeks risiko ini resmi?"):
        st.write(
            "Bukan. Ini indeks sederhana untuk membandingkan kecamatan. IRBI resmi dari BNPB "
            "disusun per kabupaten/kota dengan metodologi yang berbeda."
        )
    with st.expander("Mengapa ada kecamatan yang tidak muncul?"):
        st.write(
            "Kalau data meteorologi diunggah, hanya kecamatan yang punya data bencana dan data "
            "meteorologi sekaligus yang ditampilkan. Kecamatan lainnya disebutkan di sidebar."
        )
    with st.expander("Format data apa yang bisa diunggah?"):
        st.write(
            "CSV. Data bencana bisa berupa laporan BPBD apa adanya atau tabel sederhana dengan kolom "
            "tanggal, jenis_bencana, kecamatan. Data meteorologi minimal berisi kecamatan dan curah hujan. "
            "Bisa satu file, beberapa file, atau satu folder."
        )
    with st.expander("Apa bedanya Dashboard Utama dan Peta Analisis 2026?"):
        st.write(
            "Dashboard Utama dibuat otomatis dari data yang diunggah dan bisa difilter. Peta Analisis 2026 "
            "berisi peta yang disiapkan terpisah, satu untuk setiap jenis bencana."
        )

    st.info(
        "**Catatan.** Dashboard ini masih prototipe. Koordinat pusat kecamatan hanya perkiraan, keparahan "
        "dan indeks risiko adalah proksi, dan data meteorologi yang belum diunggah masih simulasi. "
        "Sesuaikan sumber data dan metodenya sebelum dipakai untuk laporan resmi."
    )

    st.markdown("### Tentang penyusun")
    st.markdown(
        "Dikembangkan oleh mahasiswa **Departemen Geofisika dan Meteorologi, IPB University**. "
        "Sumber rujukan: **BPBD Kabupaten Bogor** (data kejadian bencana) dan "
        "**BMKG** (klasifikasi intensitas hujan dan data meteorologi)."
    )
    if TIM_PENYUSUN:
        st.markdown("**Tim penyusun:**\n" + "\n".join(f"- {nama}" for nama in TIM_PENYUSUN))
    if KONTAK_EMAIL:
        st.markdown(f"**Kontak:** {KONTAK_EMAIL}")

    st.markdown("---")
    st.markdown(
        '<div class="home-footer">© 2026 Departemen Geofisika dan Meteorologi, IPB University · '
        "Prototipe untuk keperluan akademik</div>",
        unsafe_allow_html=True,
    )


# Peta analisis 2026 tidak digambar dari data di atas, tapi berupa file hasil
# analisis terpisah (QGIS/ArcGIS/dll). Taruh di folder peta_analisis/ dengan
# nama peta_<jenis>_2026.<png/jpg/jpeg/html>, mis. peta_tanah_longsor_2026.png


def slug_jenis_peta(nama):
    return nama.strip().lower().replace(" ", "_")


def cari_file_peta(jenis):
    slug = slug_jenis_peta(jenis)
    for ext in ["png", "jpg", "jpeg", "html"]:
        path = os.path.join(PETA_ANALISIS_DIR, f"peta_{slug}_2026.{ext}")
        if os.path.exists(path):
            return path, ext
    return None, None


tab_home, tab_utama, tab_peta_2026 = st.tabs(["Home", "Dashboard Utama", "Peta Analisis 2026"])

with tab_home:
    halaman_home(df_all, kecamatan_aktif, ada_data_bencana, ada_data_meteo)

with tab_utama:
    # --- Header dan KPI ---
    st.markdown("## Pemantauan Bencana — Kabupaten Bogor")
    st.markdown(
        '<p class="dash-caption">Departemen Geofisika dan Meteorologi, IPB University · '
        "cakupan Kabupaten Bogor.</p>",
        unsafe_allow_html=True,
    )
    if not ada_data_bencana or not ada_data_meteo:
        bagian_kurang = []
        if not ada_data_bencana:
            bagian_kurang.append("kejadian bencana")
        if not ada_data_meteo:
            bagian_kurang.append("meteorologi")
        st.markdown(
            '<div class="proto-note">📌 Data ' + " & ".join(bagian_kurang) + " masih <b>simulasi</b>. "
            "Unggah CSV di sidebar untuk melihat data sebenarnya.</div>",
            unsafe_allow_html=True,
        )
    elif len(kecamatan_aktif) < len(KECAMATAN_BOGOR):
        st.markdown(
            f'<div class="proto-note">📌 Dashboard hanya menampilkan <b>{len(kecamatan_aktif)} dari '
            f"{len(KECAMATAN_BOGOR)} kecamatan</b>. Kecamatan lain belum punya data bencana <i>dan</i> "
            "meteorologi sekaligus (lihat sidebar).</div>",
            unsafe_allow_html=True,
        )

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total kejadian", f"{len(df):,}".replace(",", "."))
    col2.metric("Korban meninggal", f"{int(df['meninggal'].sum()):,}".replace(",", "."))
    col3.metric("Korban mengungsi", f"{int(df['mengungsi'].sum()):,}".replace(",", "."))
    col4.metric("Rumah terdampak", f"{int(df['rumah_terdampak'].sum()):,}".replace(",", "."))
    n_tinggi = int((df_risk["kategori_risiko"] == "Tinggi").sum())
    col5.metric("Kecamatan risiko tinggi", f"{n_tinggi} / {len(kecamatan_aktif)}")

    st.markdown("---")

    # --- Peta sebaran, tren, komposisi ---
    left, right = st.columns([1.55, 1])

    with left:
        st.markdown("#### Sebaran titik kejadian")
        st.caption(
            "Ukuran titik = indeks keparahan. Basemap OpenStreetMap (butuh internet). "
            "Titik tanpa koordinat asli ditempatkan di sekitar titik tengah kecamatan."
        )
        fig_map = go.Figure()
        for jenis in jenis_opsi:
            sub = df[df["jenis_bencana"] == jenis]
            if sub.empty:
                continue
            fig_map.add_trace(
                go.Scattermap(
                    lat=sub["lat"],
                    lon=sub["lon"],
                    mode="markers",
                    name=jenis,
                    text=sub.apply(
                        lambda r: f"{r['jenis_bencana']}<br>{r['kecamatan']}<br>{r['tanggal'].strftime('%d %b %Y')}",
                        axis=1,
                    ),
                    hoverinfo="text",
                    marker=dict(size=(sub["keparahan"] * 3.2 + 6), color=PALETTE.get(jenis, "#999999"), opacity=0.85),
                )
            )
        fig_map.update_layout(
            map=dict(style="open-street-map", center=MAP_CENTER, zoom=MAP_ZOOM),
            margin=dict(l=0, r=0, t=0, b=0),
            height=420,
            legend=dict(orientation="h", y=-0.03),
        )
        st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("#### Tren bulanan")
        st.caption("Jumlah kejadian per bulan menurut jenis bencana.")
        df_trend = df.copy()
        df_trend["bulan"] = df_trend["tanggal"].dt.to_period("M").astype(str)
        trend_agg = df_trend.groupby(["bulan", "jenis_bencana"]).size().reset_index(name="jumlah")
        fig_trend = px.bar(
            trend_agg, x="bulan", y="jumlah", color="jenis_bencana", color_discrete_map=PALETTE,
            labels={"bulan": "", "jumlah": "Jumlah kejadian", "jenis_bencana": "Jenis"},
        )
        fig_trend.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig_trend, use_container_width=True)

    with right:
        st.markdown("#### Komposisi jenis bencana")
        comp = df["jenis_bencana"].value_counts().reset_index()
        comp.columns = ["jenis_bencana", "jumlah"]
        fig_comp = px.pie(
            comp, names="jenis_bencana", values="jumlah", hole=0.55,
            color="jenis_bencana", color_discrete_map=PALETTE,
        )
        fig_comp.update_layout(height=230, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="")
        st.plotly_chart(fig_comp, use_container_width=True)

        st.markdown("#### Sebaran per kecamatan")
        st.caption("10 kecamatan dengan kejadian terbanyak.")
        kec_rank = df["kecamatan"].value_counts().head(10).sort_values().reset_index()
        kec_rank.columns = ["kecamatan", "jumlah"]
        fig_kec = px.bar(kec_rank, x="jumlah", y="kecamatan", orientation="h", color_discrete_sequence=["#E1863C"])
        fig_kec.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), showlegend=False)
        st.plotly_chart(fig_kec, use_container_width=True)

    st.markdown("---")

    # --- Korelasi curah hujan vs kejadian ---
    st.markdown("#### Korelasi curah hujan vs kejadian bencana per kecamatan")
    st.caption(
        "Sumbu X: curah hujan rata-rata (mm/hari). Sumbu Y: jumlah kejadian hidrometeorologi "
        "(banjir, tanah longsor, angin kencang, kekeringan). Ukuran titik: total kejadian semua jenis. "
        "Warna: kategori indeks risiko (bukan IRBI resmi)."
    )

    hidro_count = (
        df[df["jenis_bencana"].isin(HIDROMETEOROLOGI)]
        .groupby("kecamatan").size().reset_index(name="kejadian_hidrometeorologi")
    )
    corr_df = df_risk.merge(hidro_count, on="kecamatan", how="left").fillna({"kejadian_hidrometeorologi": 0})

    fig_corr = px.scatter(
        corr_df,
        x="curah_hujan_mm_hari",
        y="kejadian_hidrometeorologi",
        size="jumlah_kejadian",
        color="kategori_risiko",
        color_discrete_map=RISK_COLOR,
        hover_name="kecamatan",
        hover_data={"indeks_risiko": True, "rata_keparahan": ":.1f", "jumlah_kejadian": True,
                    "curah_hujan_mm_hari": ":.1f", "kejadian_hidrometeorologi": True},
        labels={
            "curah_hujan_mm_hari": "Curah hujan rata-rata (mm/hari)",
            "kejadian_hidrometeorologi": "Jumlah kejadian hidrometeorologi",
            "kategori_risiko": "Indeks risiko",
        },
        size_max=32,
    )

    # regresi linear (kuadrat terkecil) dan R², dihitung pakai numpy
    x_vals = corr_df["curah_hujan_mm_hari"].to_numpy(dtype=float)
    y_vals = corr_df["kejadian_hidrometeorologi"].to_numpy(dtype=float)

    r_squared = np.nan
    if len(x_vals) >= 2 and np.std(x_vals) > 0:
        slope, intercept = np.polyfit(x_vals, y_vals, 1)
        y_pred = slope * x_vals + intercept
        ss_res = np.sum((y_vals - y_pred) ** 2)
        ss_tot = np.sum((y_vals - y_vals.mean()) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
        r_koefisien = np.sign(slope) * np.sqrt(r_squared)

        x_garis = np.linspace(x_vals.min(), x_vals.max(), 50)
        fig_corr.add_trace(
            go.Scatter(
                x=x_garis, y=slope * x_garis + intercept, mode="lines", name="Garis regresi",
                line=dict(color="#5E6B7A", width=2, dash="dash"), hoverinfo="skip",
            )
        )
        fig_corr.add_annotation(
            xref="paper", yref="paper", x=0.02, y=0.98, xanchor="left", yanchor="top",
            showarrow=False,
            text=f"R² = {r_squared:.3f}  (r = {r_koefisien:.3f})<br>y = {slope:.3f}x + {intercept:.2f}",
            font=dict(size=12, color="#3A4552"),
            align="left", bgcolor="rgba(255,255,255,0.75)",
            bordercolor="rgba(127,127,127,0.35)", borderwidth=1, borderpad=6,
        )

    fig_corr.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), legend_title_text="Indeks risiko")
    st.plotly_chart(fig_corr, use_container_width=True)

    if not np.isnan(r_squared):
        if r_squared >= 0.64:
            kekuatan = "kuat"
        elif r_squared >= 0.36:
            kekuatan = "sedang"
        elif r_squared >= 0.09:
            kekuatan = "lemah"
        else:
            kekuatan = "sangat lemah / tidak ada"
        arah = "positif" if r_koefisien >= 0 else "negatif"
        st.caption(
            f"R² = {r_squared:.3f}, artinya sekitar {r_squared*100:.1f}% variasi jumlah kejadian "
            f"hidrometeorologi antar-kecamatan bisa dijelaskan secara linear oleh curah hujan. "
            f"Hubungannya {arah} dengan kekuatan **{kekuatan}** "
            "(patokan kasar: < 0,09 sangat lemah, 0,09–0,36 lemah, 0,36–0,64 sedang, > 0,64 kuat). "
            f"Ini korelasi sederhana, bukan bukti sebab-akibat, dan baru memakai {len(kecamatan_aktif)} titik data."
        )
    else:
        st.caption("R² belum bisa dihitung karena curah hujan tidak bervariasi atau titik data kurang dari 2.")

    st.markdown("---")

    # --- Indikator meteorologi ---
    st.markdown("#### Indikator meteorologi")
    st.caption(
        f"Rata-rata untuk {len(kecamatan_aktif)} kecamatan dengan data lengkap."
        if meteo_dari_file else
        "Rata-rata seluruh kecamatan (data simulasi)."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Curah Hujan (mm/hari)", f"{df_meteo['curah_hujan_mm_hari'].mean():.1f}")
    m2.metric("Suhu (°C)", f"{df_meteo['suhu_c'].mean():.1f}")
    m3.metric("Kelembaban (%)", f"{df_meteo['kelembaban_persen'].mean():.0f}")
    m4.metric("Kecepatan Angin (km/jam)", f"{df_meteo['kecepatan_angin_kmh'].mean():.1f}")

    tab1, tab2 = st.tabs(["Curah hujan per kecamatan", "Tabel indikator lengkap"])

    with tab1:
        meteo_sorted = df_meteo.sort_values("curah_hujan_mm_hari", ascending=True)
        fig_meteo = px.bar(
            meteo_sorted, x="curah_hujan_mm_hari", y="kecamatan", orientation="h",
            color="kategori_intensitas",
            color_discrete_map={
                "Tidak Hujan/Berawan": "#8A96A5", "Ringan": "#3FA79E",
                "Sedang": "#D9A441", "Lebat": "#E1863C", "Sangat Lebat": "#E8543F",
                "Tidak Diketahui": "#5E6B7A",
            },
            labels={"curah_hujan_mm_hari": "Curah hujan (mm/hari)", "kecamatan": "", "kategori_intensitas": "Kategori"},
        )
        fig_meteo.update_layout(
            height=max(220, 36 * len(meteo_sorted)),
            margin=dict(l=10, r=10, t=10, b=10), legend_title_text="",
        )
        st.plotly_chart(fig_meteo, use_container_width=True)

    with tab2:
        tabel_meteo = df_meteo[
            ["kecamatan", "curah_hujan_mm_hari", "kategori_intensitas", "suhu_c", "kelembaban_persen", "kecepatan_angin_kmh"]
        ].sort_values("curah_hujan_mm_hari", ascending=False)
        tabel_meteo.columns = ["Kecamatan", "Curah Hujan (mm/hari)", "Kategori", "Suhu (°C)", "Kelembaban (%)", "Angin (km/jam)"]
        st.dataframe(tabel_meteo, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Log kejadian ---
    st.markdown("#### Log kejadian terbaru")
    log_cols = ["tanggal", "jenis_bencana", "kecamatan", "meninggal", "mengungsi", "rumah_terdampak", "status"]
    df_log = df.sort_values("tanggal", ascending=False)[log_cols].head(30).copy()
    df_log["tanggal"] = df_log["tanggal"].dt.strftime("%d %b %Y")
    df_log.columns = ["Tanggal", "Jenis", "Kecamatan", "Meninggal", "Mengungsi", "Rumah Terdampak", "Status"]
    st.dataframe(df_log, use_container_width=True, hide_index=True)

    st.caption("Indeks risiko hanya komposit sederhana untuk prototipe. Sesuaikan metodenya sebelum dipakai untuk laporan resmi.")

with tab_peta_2026:
    st.markdown("### Peta Hasil Analisis Bencana 2026")
    st.caption(
        "Peta hasil analisis kebencanaan Kabupaten Bogor tahun 2026 per jenis bencana. "
        "Peta ini disiapkan terpisah, bukan digambar dari data di tab \"Dashboard Utama\"."
    )

    jenis_peta_pilih = st.radio("Pilih jenis bencana", JENIS_PETA_2026, horizontal=True, key="peta2026_jenis")

    path_peta, ext_peta = cari_file_peta(jenis_peta_pilih)
    if path_peta is None:
        st.warning(
            f"Berkas peta **{jenis_peta_pilih}** belum ditemukan. Taruh file di folder "
            f"`{PETA_ANALISIS_DIR}/` dengan nama `peta_{slug_jenis_peta(jenis_peta_pilih)}_2026.png` "
            "(atau .jpg/.jpeg untuk gambar, .html untuk peta interaktif)."
        )
    elif ext_peta == "html":
        with open(path_peta, "r", encoding="utf-8") as f:
            html_peta = f.read()
        st.components.v1.html(html_peta, height=650, scrolling=True)
    else:
        st.image(
            path_peta,
            caption=f"Peta {jenis_peta_pilih} — Kabupaten Bogor, 2026",
            use_container_width=True,
        )
