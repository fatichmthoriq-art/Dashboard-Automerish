"""Automeris ML - aplikasi perapian data uji bending (UTM -> data rapi + grafik gaya Origin).
Jalankan:  streamlit run app.py"""
import io
import os
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import streamlit as st

import core

st.set_page_config(page_title='Automeris ML - Uji Bending', page_icon='📈', layout='wide')
DIR = Path(__file__).parent
MODEL_DEFAULT = DIR / 'model' / 'model_automeris_bending.joblib'


@st.cache_resource(show_spinner='Memuat model...')
def muat_model(sumber):
    paket = joblib.load(sumber)
    for k in ('model', 'aturan', 'win', 'kolom'):
        if k not in paket:
            raise ValueError(f'File model tidak lengkap (tidak ada "{k}")')
    return paket


# ============================================================================ sidebar: model
st.sidebar.title('📈 Automeris ML')
st.sidebar.caption('Perapian data uji bending otomatis')

paket = None
if MODEL_DEFAULT.exists():
    paket = muat_model(str(MODEL_DEFAULT))
    st.sidebar.success(f'Model dimuat: {MODEL_DEFAULT.name}')
up_model = st.sidebar.file_uploader('Ganti / unggah model (.joblib)', type=['joblib'])
if up_model is not None:
    try:
        paket = muat_model(io.BytesIO(up_model.getvalue()))
        st.sidebar.success(f'Model dimuat: {up_model.name}')
    except Exception as e:
        st.sidebar.error(f'Gagal memuat model: {e}')

if paket is None:
    st.title('Automeris ML - Uji Bending')
    st.warning('Model belum ada. Unggah file **model_automeris_bending.joblib** hasil notebook Colab '
               'di sidebar, atau taruh file itu di folder `model/` di samping `app.py`.')
    st.stop()

A = paket['aturan']

# ============================================================================ sidebar: pengaturan
st.sidebar.header('⚙️ Pengaturan')
mode_step = st.sidebar.radio('Interval elongation', ['Otomatis', 'Manual'], horizontal=True)
step = 'auto'
if mode_step == 'Manual':
    step = st.sidebar.number_input('Interval (mm)', min_value=0.0001, value=0.05, step=0.01, format='%.4f')

mulai_nol = st.sidebar.checkbox('Mulai dari titik (0, 0)', value=bool(A.get('mulai_nol', True)))
frac_def = A.get('potong_frac') or 0.4
potong = st.sidebar.checkbox('Potong otomatis saat spesimen patah', value=A.get('potong_frac') is not None)
frac = st.sidebar.slider('Potong saat beban turun di bawah (% beban puncak)', 5, 95,
                         int(round(frac_def * 100)), disabled=not potong) / 100

c1, c2 = st.sidebar.columns(2)
satuan_x = c1.selectbox('Satuan X', list(core.SATUAN_X), index=0)
satuan_y = c2.selectbox('Satuan Y', list(core.SATUAN_Y), index=0)
c3, c4 = st.sidebar.columns(2)
dx = c3.number_input('Desimal X', 0, 6, int(A.get('desimal_x', 3)))
dy = c4.number_input('Desimal Y', 0, 6, int(A.get('desimal_y', 2)))

st.sidebar.header('🖼️ Tampilan')
tampil_mentah = st.sidebar.checkbox('Tampilkan titik data mentah', value=True)
pakai_ml = st.sidebar.checkbox('Gunakan koreksi model ML', value=True,
                               help='Matikan untuk membandingkan dengan interpolasi biasa.')
dpi = st.sidebar.select_slider('Resolusi PNG (dpi)', [150, 300, 600], value=300)

with st.sidebar.expander('Aturan bawaan model'):
    st.json(A)

# ============================================================================ halaman utama
st.title('Automeris ML - Uji Bending')
st.write('Unggah file data mentah mesin UTM (Excel/CSV). Kolom **Elongation** dan **Force** dikenali otomatis. '
         'Bisa banyak file sekaligus.')

files = st.file_uploader('File data mentah', type=['xlsx', 'xls', 'xlsm', 'csv', 'txt', 'tsv'],
                         accept_multiple_files=True)
if not files:
    st.info('Belum ada file. Contoh format: kolom `No.`, `Time( min)`, `Elongation( mm)`, `Force( N)`.')
    st.stop()

hasil, gagal = [], []
with st.spinner('Merapikan data...'):
    for f in files:
        try:
            ks = core.kurva_dari_file(f.name, f.getvalue())
            if not ks:
                gagal.append((f.name, 'kolom Elongation/Force tidak ditemukan')); continue
            for j, k in enumerate(ks):
                nama = Path(f.name).stem + (f' [{k["sheet"]}]' if len(ks) > 1 else '')
                df = core.rapikan(k['x'], k['y'], paket, step=step, mulai_nol=mulai_nol, potong=potong,
                                  potong_frac=frac, satuan_x=satuan_x, satuan_y=satuan_y,
                                  desimal_x=dx, desimal_y=dy, pakai_ml=pakai_ml)
                hasil.append(dict(nama=nama, df=df,
                                  x_raw=k['x'] * core.SATUAN_X[satuan_x], y_raw=k['y'] * core.SATUAN_Y[satuan_y],
                                  kolom=f"{k['kolom_x']} / {k['kolom_y']}"))
        except Exception as e:
            gagal.append((f.name, f'{type(e).__name__}: {e}'))

for n, e in gagal:
    st.error(f'❌ {n}: {e}')
if not hasil:
    st.stop()

# ---------------------------------------------------------------------------- ringkasan
rk = pd.DataFrame([{'Spesimen': h['nama'], **core.ringkasan(h['df'])} for h in hasil])
rk = rk.rename(columns={'F maks': f'F maks ({satuan_y})', 'Elongation saat F maks': f'Elongation saat F maks ({satuan_x})',
                        'Elongation akhir': f'Elongation akhir ({satuan_x})'})
m1, m2, m3 = st.columns(3)
m1.metric('Spesimen diproses', len(hasil))
m2.metric(f'Rata-rata F maks ({satuan_y})', f'{rk.iloc[:, 1].mean():,.2f}')
m3.metric(f'Std. deviasi F maks ({satuan_y})', f'{rk.iloc[:, 1].std(ddof=1) if len(rk) > 1 else 0:,.2f}')

tab1, tab2, tab3 = st.tabs(['📊 Grafik gabungan', '🔍 Per spesimen', '📋 Ringkasan'])

with tab1:
    pilih = st.multiselect('Spesimen yang ditampilkan', [h['nama'] for h in hasil],
                           default=[h['nama'] for h in hasil][:8])
    seri = [h for h in hasil if h['nama'] in pilih]
    if seri:
        judul = st.text_input('Judul grafik', 'Load vs Elongation')
        fig = core.plot_origin(seri, judul, tampil_mentah)
        st.pyplot(fig)
        st.download_button('⬇️ Unduh grafik gabungan (PNG)', core.fig_ke_png(fig, dpi), 'grafik_gabungan.png', 'image/png')

with tab2:
    nama = st.selectbox('Pilih spesimen', [h['nama'] for h in hasil])
    h = next(h for h in hasil if h['nama'] == nama)
    ca, cb = st.columns([3, 2])
    with ca:
        fig = core.plot_origin([h], h['nama'], tampil_mentah)
        st.pyplot(fig)
    with cb:
        st.caption(f"Kolom terbaca: {h['kolom']}")
        st.dataframe(h['df'], height=360)
    buf = io.BytesIO(); h['df'].to_excel(buf, index=False)
    d1, d2 = st.columns(2)
    d1.download_button('⬇️ Excel spesimen ini', buf.getvalue(), f"{h['nama']}_rapi.xlsx")
    d2.download_button('⬇️ Grafik spesimen ini (PNG)', core.fig_ke_png(fig, dpi), f"{h['nama']}_grafik.png", 'image/png')

with tab3:
    st.dataframe(rk.round(4), hide_index=True)

# ---------------------------------------------------------------------------- unduh semua
st.divider()


def buat_zip():
    z = io.BytesIO()
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        gab = io.BytesIO()
        with pd.ExcelWriter(gab, engine='openpyxl') as w:
            rk.to_excel(w, sheet_name='Ringkasan', index=False)
            for h in hasil:
                h['df'].to_excel(w, sheet_name=h['nama'][:31].replace('/', '_').replace('[', '(').replace(']', ')'), index=False)
        zf.writestr('semua_spesimen.xlsx', gab.getvalue())
        zf.writestr('grafik_gabungan.png', core.fig_ke_png(core.plot_origin(hasil[:8], 'Load vs Elongation', tampil_mentah), dpi))
        for h in hasil:
            b = io.BytesIO(); h['df'].to_excel(b, index=False)
            zf.writestr(f"excel/{h['nama']}_rapi.xlsx", b.getvalue())
            zf.writestr(f"grafik/{h['nama']}.png", core.fig_ke_png(core.plot_origin([h], h['nama'], tampil_mentah), dpi))
    return z.getvalue()


st.download_button('📦 Unduh SEMUA hasil (ZIP: Excel gabungan + Excel & grafik per spesimen)',
                   buat_zip(), 'hasil_automeris_ml.zip', 'application/zip', type='primary')
