"""AutoMeris ML - pengolahan kurva uji mekanik (bending / tarik).
Dua sumber data: (1) file mesin UTM, (2) gambar grafik (digitasi otomatis).
Jalankan:  streamlit run app.py"""
import io
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import core
import digitizer as dg
import themes

st.set_page_config(page_title='AutoMeris ML', page_icon='📈', layout='wide', initial_sidebar_state='expanded')
DIR = Path(__file__).parent
MODEL_DEFAULT = DIR / 'model' / 'model_automeris_bending.joblib'
SERI = core.WARNA


@st.cache_resource(show_spinner=False)
def muat_model(sumber):
    paket = joblib.load(sumber)
    for k in ('model', 'aturan', 'win', 'kolom'):
        if k not in paket:
            raise ValueError(f'file model tidak lengkap ("{k}" tidak ada)')
    return paket


# ============================================================================ SIDEBAR
with st.sidebar:
    st.markdown('### 📈 AutoMeris ML')
    st.caption('Pengolahan kurva uji mekanik')
    desain = st.selectbox('Desain dashboard', list(themes.TEMA), index=0,
                          help='\n\n'.join(f'**{k}**: {v["desk"]}' for k, v in themes.TEMA.items()))

    with st.expander('Pengolahan kurva', expanded=True):
        awal_lbl = st.radio('Titik awal kurva', ['Mulai (0,0), buang toe', 'Kompensasi toe (ASTM)', 'Data asli'],
                            help='**Mulai (0,0)**: gelombang beban kecil di awal (slack/toe) dibuang, kurva ditarik dari titik nol.\n\n'
                                 '**Kompensasi toe**: garis elastis diperpanjang ke F = 0 dan seluruh kurva digeser (cara standar ASTM E8/D790).\n\n'
                                 '**Data asli**: awal kurva tidak diubah.')
        awal = {'Mulai (0,0), buang toe': 'nol', 'Kompensasi toe (ASTM)': 'toe', 'Data asli': 'asli'}[awal_lbl]
        patah_lbl = st.selectbox('Titik patah', ['Otomatis', 'Saat beban < % puncak', 'Tidak dipotong'])
        patah = {'Otomatis': 'otomatis', 'Saat beban < % puncak': 'fraksi', 'Tidak dipotong': 'tidak'}[patah_lbl]
        frac = st.slider('Batas beban (% puncak)', 5, 95, 40, disabled=patah != 'fraksi') / 100
        kehalusan = st.slider('Kehalusan kurva', 0, 10, 6,
                              help='0 = mengikuti data mentah, 10 = sangat halus. 5-7 cocok untuk kebanyakan data UTM.')
        mode_step = st.radio('Interval data keluaran', ['Otomatis', 'Manual'], horizontal=True)
        step = 'auto' if mode_step == 'Otomatis' else st.number_input('Interval elongation (mm)', 0.0001, 10.0, 0.01, 0.005, format='%.4f')

    with st.expander('Format keluaran'):
        jenis = st.radio('Jenis kurva', ['Force - Elongation', 'Stress - Strain'], horizontal=True)
        teg = None
        if jenis == 'Stress - Strain':
            c1, c2 = st.columns(2)
            A0 = c1.number_input('Luas A₀ (mm²)', 0.001, 1e6, 12.5, format='%.3f')
            L0 = c2.number_input('Panjang ukur L₀ (mm)', 0.001, 1e5, 50.0, format='%.2f')
            teg = dict(A0=A0, L0=L0)
            satuan_x, satuan_y = 'mm', 'N'
        else:
            c1, c2 = st.columns(2)
            satuan_x = c1.selectbox('Satuan X', list(core.SATUAN_X))
            satuan_y = c2.selectbox('Satuan Y', list(core.SATUAN_Y))
        c3, c4 = st.columns(2)
        dx = c3.number_input('Desimal X', 0, 6, 3)
        dy = c4.number_input('Desimal Y', 0, 6, 2)

    with st.expander('Model ML (opsional)'):
        paket = None
        if MODEL_DEFAULT.exists():
            try:
                paket = muat_model(str(MODEL_DEFAULT))
            except Exception as e:
                st.error(f'Model bawaan gagal dimuat: {e}')
        up = st.file_uploader('Unggah model (.joblib)', type=['joblib'], label_visibility='collapsed')
        if up is not None:
            try:
                paket = muat_model(io.BytesIO(up.getvalue()))
            except Exception as e:
                st.error(f'Gagal memuat model: {e}')
        st.caption('Model dimuat ✓' if paket else 'Belum ada model. Aplikasi tetap berjalan dengan smoothing presisi.')
        pakai_ml = st.toggle('Terapkan koreksi gaya Origin (ML)', value=False, disabled=paket is None,
                             help='Menambahkan koreksi bentuk hasil belajar dari grafik Origin. '
                                  'Aplikasi memberi peringatan bila koreksi mengubah F maks lebih dari 3%.')

    with st.expander('Tampilan & ekspor'):
        tampil_mentah = st.toggle('Tampilkan data mentah sebagai pembanding', value=False)
        dpi = st.select_slider('Resolusi PNG (dpi)', [150, 300, 600], value=300)

(st.html if hasattr(st, 'html') else (lambda h: st.markdown(h, unsafe_allow_html=True)))(themes.css(desain))
st.markdown(themes.header(desain, 'AutoMeris ML', 'Data uji bending & tarik → kurva rapi, tabel Excel, dan grafik siap laporan',
                          'Model ML aktif' if (paket and pakai_ml) else 'Smoothing presisi', aktif=bool(paket and pakai_ml)),
            unsafe_allow_html=True)

kw = dict(awal=awal, patah=patah, frac=frac, kehalusan=kehalusan, step=step, paket=paket, pakai_ml=pakai_ml)
fmt = dict(satuan_x=satuan_x, satuan_y=satuan_y, desimal_x=dx, desimal_y=dy, tegangan=teg)


# ============================================================================ HASIL (dipakai kedua tab)
def olah(nama, x, y):
    xg, yg, info = core.proses(x, y, **kw)
    df = core.ke_tabel(xg, yg, **fmt)
    if teg:
        xr, yr = np.asarray(x) / teg['L0'] * 100, np.asarray(y) / teg['A0']
    else:
        xr, yr = np.asarray(x) * core.SATUAN_X[satuan_x], np.asarray(y) * core.SATUAN_Y[satuan_y]
    return dict(nama=nama, df=df, x_raw=xr, y_raw=yr, info=info)


def fmt_angka(v, d=2):
    return f'{v:,.{d}f}'.replace(',', '§').replace('.', ',').replace('§', '.')


def ringkasan(hasil):
    rows = []
    for h in hasil:
        x, y = h['df'].iloc[:, 0].to_numpy(), h['df'].iloc[:, 1].to_numpy(); ip = int(np.argmax(y))
        rows.append({'Spesimen': h['nama'], f'{h["df"].columns[1]} maks': y[ip], f'{h["df"].columns[0]} saat maks': x[ip],
                     f'{h["df"].columns[0]} patah': x[-1], 'Energi (J)': h['info']['energi'],
                     'Kekakuan (N/mm)': h['info']['kekakuan'], 'Δ maks vs mentah (%)': h['info']['selisih_F_maks']})
    return pd.DataFrame(rows)


def grafik(hasil, judul):
    fig = go.Figure()
    for i, h in enumerate(hasil):
        c = SERI[i % len(SERI)]
        if tampil_mentah:
            fig.add_trace(go.Scattergl(x=h['x_raw'], y=h['y_raw'], mode='markers', name=f'{h["nama"]} (mentah)',
                                       marker=dict(size=4, color='#b8b8b8'), showlegend=i == 0, legendgroup='mentah',
                                       hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=h['df'].iloc[:, 0], y=h['df'].iloc[:, 1], mode='lines', name=h['nama'],
                                 line=dict(color=c, width=2.2),
                                 hovertemplate='%{y:,.2f}<extra>' + h['nama'] + '</extra>'))
    lay = themes.plotly_layout(desain)
    lay['xaxis']['title'] = hasil[0]['df'].columns[0]; lay['yaxis']['title'] = hasil[0]['df'].columns[1]
    fig.update_layout(**lay)
    return fig


def tampilkan_hasil(hasil, kunci, judul_default):
    df_r = ringkasan(hasil)
    kol_y = df_r.columns[1]; kol_xm = df_r.columns[2]; kol_xp = df_r.columns[3]
    sat_y = kol_y.split('(')[-1].split(')')[0]; sat_x = kol_xp.split('(')[-1].split(')')[0]
    ym = df_r[kol_y]; n = len(df_r)
    st.markdown(themes.kpi([
        ('Spesimen', f'{n}', 'kurva diproses'),
        (f'{kol_y.split(" (")[0]} maks' + (' rata-rata' if n > 1 else ''), fmt_angka(ym.mean()), (f'± {fmt_angka(ym.std(ddof=1))} {sat_y} (SD)' if n > 1 else sat_y)),
        ('Saat beban maks', fmt_angka(df_r[kol_xm].mean(), 3), f'{sat_x}, rata-rata'),
        ('Titik patah', fmt_angka(df_r[kol_xp].mean(), 3), f'{sat_x}, rata-rata'),
        ('Energi', fmt_angka(df_r['Energi (J)'].mean(), 3), 'J, luas di bawah kurva'),
    ]), unsafe_allow_html=True)

    if pakai_ml and (df_r['Δ maks vs mentah (%)'].abs() > 3).any():
        st.markdown('<div class="am-warn">⚠️ Koreksi ML mengubah beban maksimum lebih dari 3% dari data terukur pada '
                    'sebagian spesimen. Untuk laporan resmi, matikan koreksi ML agar nilai puncak sesuai hasil pengujian.</div>',
                    unsafe_allow_html=True)

    kiri, kanan = st.columns([1.65, 1], gap='medium')
    with kiri:
        with st.container(border=True):
            nama_all = [h['nama'] for h in hasil]
            c1, c2 = st.columns([2, 1.2])
            pilih = c1.multiselect('Spesimen ditampilkan', nama_all, default=nama_all[:8], key=f'{kunci}_pilih')
            judul = c2.text_input('Judul grafik (untuk PNG)', judul_default, key=f'{kunci}_judul')
            seri = [h for h in hasil if h['nama'] in pilih] or hasil[:1]
            st.markdown(f'<div class="am-sec" style="margin-top:6px">{judul}</div>', unsafe_allow_html=True)
            st.plotly_chart(grafik(seri, ''), width='stretch', config={'displaylogo': False},
                            key=f'{kunci}_plot')
    with kanan:
        with st.container(border=True):
            st.markdown('<div class="am-sec">Ringkasan per spesimen</div>', unsafe_allow_html=True)
            tampil = df_r.set_index('Spesimen')[[kol_y, kol_xm, kol_xp, 'Energi (J)']].round(3)
            tampil.columns = [f'Maks ({sat_y})', f'Saat maks ({sat_x})', f'Patah ({sat_x})', 'Energi (J)']
            st.dataframe(tampil, height=250)
            st.markdown('<div class="am-sec" style="margin-top:14px">Data hasil</div>', unsafe_allow_html=True)
            nm = st.selectbox('Spesimen', nama_all, key=f'{kunci}_tabel', label_visibility='collapsed')
            h = next(h for h in hasil if h['nama'] == nm)
            st.dataframe(h['df'], height=230, hide_index=True)
            b = io.BytesIO(); h['df'].to_excel(b, index=False)
            c1, c2 = st.columns(2)
            c1.download_button('Excel', b.getvalue(), f'{nm}_rapi.xlsx', key=f'{kunci}_x1', width='stretch')
            c2.download_button('PNG', core.fig_ke_png(core.plot_origin([h], nm, tampil_mentah), dpi), f'{nm}.png',
                               'image/png', key=f'{kunci}_p1', width='stretch')

    # unduh semua
    z = io.BytesIO()
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        g = io.BytesIO()
        with pd.ExcelWriter(g, engine='openpyxl') as w:
            df_r.to_excel(w, sheet_name='Ringkasan', index=False)
            for h in hasil:
                h['df'].to_excel(w, sheet_name=''.join(ch for ch in h['nama'] if ch not in '[]:*?/\\')[:31], index=False)
        zf.writestr('semua_spesimen.xlsx', g.getvalue())
        zf.writestr('grafik_gabungan.png', core.fig_ke_png(core.plot_origin(hasil[:8], judul_default, tampil_mentah), dpi))
        for h in hasil:
            b = io.BytesIO(); h['df'].to_excel(b, index=False)
            zf.writestr(f'excel/{h["nama"]}.xlsx', b.getvalue())
            zf.writestr(f'grafik/{h["nama"]}.png', core.fig_ke_png(core.plot_origin([h], h['nama'], tampil_mentah), dpi))
    c1, c2, _ = st.columns([1.3, 1.3, 2])
    c1.download_button('⬇ Unduh semua hasil (ZIP)', z.getvalue(), 'hasil_automeris.zip', 'application/zip',
                       type='primary', key=f'{kunci}_zip', width='stretch')
    c2.download_button('⬇ Grafik gabungan (PNG)', core.fig_ke_png(core.plot_origin(seri, judul, tampil_mentah), dpi),
                       'grafik_gabungan.png', 'image/png', key=f'{kunci}_pg', width='stretch')


# ============================================================================ TAB
tab_utm, tab_img, tab_info = st.tabs(['Data mesin UTM', 'Digitasi gambar grafik', 'Panduan'])

with tab_utm:
    files = st.file_uploader('Unggah file Excel/CSV dari mesin UTM. Bisa banyak file sekaligus.',
                             type=['xlsx', 'xls', 'xlsm', 'csv', 'txt', 'tsv'], accept_multiple_files=True, key='utm')
    if not files:
        st.markdown('<div class="am-note">Kolom <b>Elongation</b> dan <b>Force</b> dikenali otomatis dari judul kolom '
                    '(contoh: <code>No.</code>, <code>Time( min)</code>, <code>Elongation( mm)</code>, <code>Force( N)</code>). '
                    'Hasil: satu kurva halus per spesimen, dipotong tepat saat patah.</div>', unsafe_allow_html=True)
    else:
        hasil, gagal = [], []
        with st.spinner('Mengolah data...'):
            for f in files:
                try:
                    ks = core.kurva_dari_file(f.name, f.getvalue())
                    if not ks:
                        gagal.append((f.name, 'kolom Elongation/Force tidak ditemukan')); continue
                    for k in ks:
                        nama = Path(f.name).stem + (f' ({k["sheet"]})' if len(ks) > 1 else '')
                        hasil.append(olah(nama, k['x'], k['y']))
                except Exception as e:
                    gagal.append((f.name, f'{type(e).__name__}: {e}'))
        for n_, e in gagal:
            st.error(f'{n_}: {e}')
        if hasil:
            tampilkan_hasil(hasil, 'utm', 'Load vs Elongation' if not teg else 'Stress vs Strain')

with tab_img:
    imgs = st.file_uploader('Unggah gambar grafik (PNG/JPG), misalnya hasil ekspor Origin, screenshot jurnal, atau scan laporan.',
                            type=['png', 'jpg', 'jpeg', 'bmp', 'tif', 'tiff'], accept_multiple_files=True, key='img')
    if not imgs:
        st.markdown('<div class="am-note">Pengganti klik manual di Automeris: sumbu dan garis kurva dicari otomatis, '
                    'angka pada sumbu dibaca dengan OCR, lalu kurva dirapikan. Batas sumbu bisa dikoreksi bila OCR keliru.</div>',
                    unsafe_allow_html=True)
    else:
        hasil_img = []
        for gi, f in enumerate(imgs):
            with st.container(border=True):
                try:
                    rgb = dg.muat(io.BytesIO(f.getvalue()))
                    bk = dg.cari_bingkai(rgb)
                except Exception as e:
                    st.error(f'{f.name}: {e}'); continue
                warna = dg.kandidat_warna(rgb, bk)
                sumbu = dg.baca_sumbu(rgb, bk)
                ka, kb = st.columns([1, 1.25], gap='medium')
                with ka:
                    st.markdown(f'<div class="am-sec">{f.name}</div>', unsafe_allow_html=True)
                    st.image(rgb, width='stretch')
                with kb:
                    st.markdown('<div class="am-sec">1 · Kurva yang diambil</div>', unsafe_allow_html=True)
                    if not warna:
                        st.error('Tidak ada garis kurva terdeteksi di dalam area grafik.'); continue
                    chips = ''.join(f'<span class="am-chip"><i style="background:rgb{w["rgb"]}"></i>{w["nama"]}</span>' for w in warna)
                    st.markdown(chips, unsafe_allow_html=True)
                    opsi = [w['nama'] for w in warna]
                    default = [w['nama'] for w in warna if w['id'] != 'hitam'][:1] or opsi[:1]
                    dipilih = st.multiselect('Pilih warna kurva', opsi, default=default, key=f'w{gi}')
                    jenis_garis = st.radio('Bentuk kurva di gambar', ['Garis', 'Titik / marker'], horizontal=True, key=f'm{gi}')
                    st.markdown('<div class="am-sec" style="margin-top:10px">2 · Batas sumbu</div>', unsafe_allow_html=True)
                    if sumbu:
                        st.caption(f'Terbaca otomatis (OCR, {sumbu["n_x"]} angka sumbu X, {sumbu["n_y"]} angka sumbu Y). Koreksi bila perlu.')
                    else:
                        st.markdown('<div class="am-warn">OCR tidak bisa membaca angka sumbu. Isi batas sumbu secara manual '
                                    '(nilai di tepi kiri/kanan dan bawah/atas kotak grafik).</div>', unsafe_allow_html=True)
                    s = sumbu or dict(x_kiri=0.0, x_kanan=1.0, y_bawah=0.0, y_atas=1.0)
                    c1, c2, c3, c4 = st.columns(4)
                    xk = c1.number_input('X kiri', value=float(round(s['x_kiri'], 4)), format='%.4f', key=f'xk{gi}')
                    xn = c2.number_input('X kanan', value=float(round(s['x_kanan'], 4)), format='%.4f', key=f'xn{gi}')
                    yb = c3.number_input('Y bawah', value=float(round(s['y_bawah'], 3)), format='%.3f', key=f'yb{gi}')
                    ya = c4.number_input('Y atas', value=float(round(s['y_atas'], 3)), format='%.3f', key=f'ya{gi}')
                    if sumbu:
                        if st.checkbox('Rapikan batas sumbu ke angka bulat terdekat (mis. -0,0051 → 0)', value=True, key=f'b{gi}'):
                            def snap(v, rng):
                                ref = 10 ** np.floor(np.log10(abs(rng) / 10)); c = float(np.round(v / ref) * ref)
                                return c if abs(v - c) < 0.005 * abs(rng) else v
                            rx, ry = xn - xk, ya - yb
                            xk, xn, yb, ya = snap(xk, rx), snap(xn, rx), snap(yb, ry), snap(ya, ry)
                    nama_dasar = st.text_input('Nama spesimen', Path(f.name).stem, key=f'n{gi}')
                for wn in dipilih:
                    w = next(w for w in warna if w['nama'] == wn)
                    try:
                        px, py = dg.ekstrak(rgb, bk, w, 'garis' if jenis_garis == 'Garis' else 'titik')
                        x, y = dg.ke_data(px, py, bk, xk, xn, yb, ya)
                        nm = nama_dasar if len(dipilih) == 1 else f'{nama_dasar} - {wn}'
                        hasil_img.append(olah(nm, x, y))
                    except Exception as e:
                        st.error(f'{wn}: {e}')
        if hasil_img:
            st.markdown('<div class="am-sec" style="margin-top:18px">Hasil digitasi</div>', unsafe_allow_html=True)
            tampilkan_hasil(hasil_img, 'img', 'Hasil digitasi')

with tab_info:
    st.markdown("""
#### Alur kerja
1. **Data mesin UTM**: unggah file Excel/CSV mentah. Setiap spesimen menjadi satu kurva halus yang dipotong saat patah.
2. **Digitasi gambar grafik**: unggah gambar grafik (Origin, jurnal, laporan). Pilih warna kurva, cek batas sumbu, dan data langsung jadi.
3. Atur pengolahan di panel kiri, lalu unduh Excel, PNG, atau ZIP semua hasil.

#### Pengaturan penting
| Pengaturan | Fungsi |
|---|---|
| **Titik awal** | *Mulai (0,0)* membuang gelombang kecil di awal (slack/toe). *Kompensasi toe* memakai cara standar ASTM: garis elastis diperpanjang ke nol dan kurva digeser. |
| **Titik patah** | *Otomatis* memotong tepat sebelum beban jatuh tajam, sehingga ekor data setelah spesimen putus dibuang. |
| **Kehalusan** | Smoothing spline. 0 = sangat mengikuti data, 10 = sangat halus. Nilai puncak tetap dijaga. |
| **Koreksi ML** | Opsional. Meniru bentuk kurva Origin dari data pelatihan. Matikan untuk laporan resmi bila diberi peringatan. |
| **Stress - Strain** | Isi luas penampang A₀ dan panjang ukur L₀ untuk mengubah kurva menjadi tegangan-regangan (MPa, %). |

#### Kolom ringkasan
*Energi* = luas di bawah kurva Force-Elongation (J). *Kekakuan* = kemiringan daerah elastis (N/mm).
*Δ maks vs mentah* = selisih beban maksimum hasil olah terhadap data mentah, sebagai pengecekan bahwa nilai puncak tidak berubah.
""")
