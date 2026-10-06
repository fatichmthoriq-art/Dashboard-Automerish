"""Tiga pilihan desain dashboard. Semua berbasis tema terang Streamlit + CSS."""

TEMA = {
    'Korporat': dict(
        desk='Biru navy, kartu putih berbayang. Kesan formal untuk laporan perusahaan.',
        bg='#f4f6fa', panel='#ffffff', sidebar='#0f2742', sidebar_teks='#e8eef7', sidebar_muted='#9fb3cc',
        teks='#14213d', muted='#5b6b82', aksen='#1f5fbf', aksen_muda='#e6efff', garis='#dde3ec',
        header_bg='linear-gradient(90deg,#0f2742 0%,#1f5fbf 100%)', header_teks='#ffffff',
        radius='10px', bayangan='0 1px 3px rgba(16,24,40,.08), 0 1px 2px rgba(16,24,40,.04)',
        font="'Inter', 'Segoe UI', sans-serif", font_url='Inter:wght@400;500;600;700',
        plot_font='Inter, Segoe UI, sans-serif', grid='#e9edf3'),
    'Industri': dict(
        desk='Header gelap arang dengan aksen oranye. Kesan teknik dan laboratorium industri.',
        bg='#f2f2f0', panel='#ffffff', sidebar='#1e1f22', sidebar_teks='#ececec', sidebar_muted='#a3a3a3',
        teks='#1e1f22', muted='#5f6064', aksen='#e8710a', aksen_muda='#fff1e5', garis='#dcdcd8',
        header_bg='#1e1f22', header_teks='#ffffff',
        radius='4px', bayangan='none',
        font="'IBM Plex Sans', 'Segoe UI', sans-serif", font_url='IBM+Plex+Sans:wght@400;500;600;700',
        plot_font='IBM Plex Sans, Segoe UI, sans-serif', grid='#ebebe7'),
    'Minimal': dict(
        desk='Putih bersih, garis tipis, aksen hijau toska. Fokus penuh ke grafik dan data.',
        bg='#ffffff', panel='#ffffff', sidebar='#fafafa', sidebar_teks='#111111', sidebar_muted='#6b6b6b',
        teks='#111111', muted='#6b6b6b', aksen='#0f8b78', aksen_muda='#e6f5f2', garis='#e6e6e6',
        header_bg='#ffffff', header_teks='#111111',
        radius='8px', bayangan='none',
        font="'Manrope', 'Segoe UI', sans-serif", font_url='Manrope:wght@400;500;600;700',
        plot_font='Manrope, Segoe UI, sans-serif', grid='#f0f0f0'),
}


def _css(nama):
    t = TEMA[nama]
    gelap_sidebar = nama != 'Minimal'
    return f"""
<link href="https://fonts.googleapis.com/css2?family={t['font_url']}&display=swap" rel="stylesheet">
<style>
:root {{ --aksen:{t['aksen']}; }}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {{ font-family:{t['font']} !important; }}
.stApp {{ background:{t['bg']}; color:{t['teks']}; }}
header[data-testid="stHeader"] {{ background:transparent; height:0; }}
.block-container {{ padding-top:1.2rem; padding-bottom:3rem; max-width:1400px; }}
#MainMenu, footer {{ visibility:hidden; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background:{t['sidebar']}; border-right:1px solid {t['garis']}; }}
section[data-testid="stSidebar"] * {{ color:{t['sidebar_teks']}; }}
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color:{t['sidebar_muted']} !important; font-size:.82rem; }}
section[data-testid="stSidebar"] [data-baseweb="select"] *, section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {{ color:{t['teks']} !important; }}
section[data-testid="stSidebar"] details summary, section[data-testid="stSidebar"] details summary:hover {{ background:transparent !important; }}
section[data-testid="stSidebar"] details summary * {{ color:{t['sidebar_teks']} !important; }}
{'section[data-testid="stSidebar"] [data-testid="stExpander"] { background:#ffffff08; border:1px solid #ffffff1a; }' if gelap_sidebar else ''}
section[data-testid="stSidebar"] [data-testid="stExpander"] {{ border-radius:{t['radius']}; }}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{ font-weight:600; color:{t['sidebar_teks']} !important; font-size:.9rem; }}

/* header aplikasi */
.am-header {{ background:{t['header_bg']}; color:{t['header_teks']}; border-radius:{t['radius']};
  padding:20px 26px; display:flex; align-items:center; justify-content:space-between; margin-bottom:18px;
  {'border:1px solid ' + t['garis'] + ';' if nama == 'Minimal' else ''} }}
.am-header h1 {{ font-size:1.45rem; font-weight:700; margin:0; color:{t['header_teks']}; letter-spacing:-.01em; padding:0; }}
.am-header p {{ margin:2px 0 0; opacity:.78; font-size:.88rem; color:{t['header_teks']}; }}
.am-badge {{ font-size:.75rem; font-weight:600; padding:5px 11px; border-radius:999px;
  background:{'#ffffff22' if nama != 'Minimal' else t['aksen_muda']}; color:{t['header_teks'] if nama != 'Minimal' else t['aksen']}; white-space:nowrap; }}
.am-badge.mati {{ background:#ffffff14; opacity:.75; }}

/* kartu KPI */
.am-kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:6px 0 18px; }}
.am-kpi {{ background:{t['panel']}; border:1px solid {t['garis']}; border-radius:{t['radius']}; padding:14px 16px; box-shadow:{t['bayangan']};
  {'border-top:3px solid ' + t['aksen'] + ';' if nama == 'Industri' else ''} }}
.am-kpi .lbl {{ font-size:.74rem; text-transform:uppercase; letter-spacing:.05em; color:{t['muted']}; font-weight:600; }}
.am-kpi .val {{ font-size:1.55rem; font-weight:700; color:{t['teks']}; margin-top:4px; font-variant-numeric:tabular-nums; }}
.am-kpi .sub {{ font-size:.78rem; color:{t['muted']}; margin-top:2px; }}

/* panel / kartu konten */
.am-sec {{ font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; font-weight:700; color:{t['muted']}; margin:4px 0 8px; }}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > .am-card-mark) {{ background:{t['panel']}; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius:{t['radius']} !important; }}

/* tab */
.stTabs [data-baseweb="tab-list"] {{ gap:4px; border-bottom:1px solid {t['garis']}; }}
.stTabs [data-baseweb="tab"] {{ height:44px; padding:0 16px; font-weight:600; color:{t['muted']}; background:transparent; }}
.stTabs [aria-selected="true"] {{ color:{t['aksen']} !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background:{t['aksen']}; height:3px; }}

/* tombol */
.stButton > button, .stDownloadButton > button {{ border-radius:{t['radius']}; font-weight:600; border:1px solid {t['garis']}; }}
.stDownloadButton > button[kind="primary"], .stButton > button[kind="primary"] {{ background:{t['aksen']}; border-color:{t['aksen']}; color:#fff; }}
.stDownloadButton > button:hover, .stButton > button:hover {{ border-color:{t['aksen']}; color:{t['aksen']}; }}
.stDownloadButton > button[kind="primary"]:hover {{ color:#fff; filter:brightness(1.08); }}

/* uploader & tabel */
[data-testid="stFileUploaderDropzone"] {{ background:{t['panel']}; border:1.5px dashed {t['garis']}; border-radius:{t['radius']}; }}
[data-testid="stFileUploaderDropzone"]:hover {{ border-color:{t['aksen']}; }}
[data-testid="stDataFrame"] {{ border:1px solid {t['garis']}; border-radius:{t['radius']}; }}
.am-note {{ background:{t['aksen_muda']}; border-left:3px solid {t['aksen']}; padding:10px 14px; border-radius:{t['radius']};
  font-size:.86rem; color:{t['teks']}; margin:8px 0; }}
.am-warn {{ background:#fff6e5; border-left:3px solid #c98500; padding:10px 14px; border-radius:{t['radius']}; font-size:.86rem; margin:8px 0; }}
.stMultiSelect [data-baseweb="tag"] {{ background:{t['aksen']} !important; }}
[data-baseweb="slider"] [role="slider"] {{ background:{t['aksen']} !important; }}
.am-chip {{ display:inline-flex; align-items:center; gap:6px; font-size:.82rem; margin-right:14px; color:{t['teks']}; }}
.am-chip i {{ width:12px; height:12px; border-radius:3px; display:inline-block; }}
</style>
"""


def css(nama):  # noqa: F811  (bungkus: buang baris kosong agar markdown tidak memutus blok HTML)
    return '\n'.join(l for l in _css(nama).splitlines() if l.strip())


def header(nama, judul, sub, badge, aktif=True):
    return (f'<div class="am-header"><div><h1>{judul}</h1><p>{sub}</p></div>'
            f'<span class="am-badge{"" if aktif else " mati"}">{badge}</span></div>')


def kpi(items):
    """items: list of (label, nilai, sub)."""
    sel = ''.join(f'<div class="am-kpi"><div class="lbl">{l}</div><div class="val">{v}</div>'
                  f'<div class="sub">{s}</div></div>' for l, v, s in items)
    return f'<div class="am-kpis">{sel}</div>'


def plotly_layout(nama):
    t = TEMA[nama]
    return dict(
        template='simple_white', font=dict(family=t['plot_font'], size=13, color=t['teks']),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=70, r=24, t=40, b=60), height=500,
        hovermode='x unified', hoverlabel=dict(bgcolor='#ffffff', font_size=12, bordercolor=t['garis']),
        legend=dict(orientation='h', yanchor='bottom', y=1.01, xanchor='left', x=0, bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(showline=True, linewidth=1.5, linecolor=t['teks'], mirror=True, ticks='inside', ticklen=6,
                   tickwidth=1.2, showgrid=True, gridcolor=t['grid'], zeroline=False, rangemode='tozero',
                   title_font=dict(size=14), minor=dict(ticks='inside', ticklen=3)),
        yaxis=dict(showline=True, linewidth=1.5, linecolor=t['teks'], mirror=True, ticks='inside', ticklen=6,
                   tickwidth=1.2, showgrid=True, gridcolor=t['grid'], zeroline=False, rangemode='tozero',
                   title_font=dict(size=14), minor=dict(ticks='inside', ticklen=3)),
    )
