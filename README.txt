AUTOMERIS ML - APLIKASI PERAPIAN DATA UJI BENDING
=================================================

ISI FOLDER
  app.py                 -> tampilan aplikasi (Streamlit)
  core.py                -> fungsi model (sama dengan notebook pelatihan)
  requirements.txt       -> daftar library
  Jalankan_Aplikasi.bat  -> klik 2x untuk membuka aplikasi (Windows)
  model/                 -> taruh model_automeris_bending.joblib di sini

LANGKAH 1 - Ambil model dari Colab
  Di notebook, setelah bagian 8 selesai, jalankan sel ini:
      from google.colab import files
      files.download('/content/hasil_ml_automeris/model_automeris_bending.joblib')
  Simpan file tersebut ke folder  model/

LANGKAH 2 - Jalankan
  Windows : klik 2x  Jalankan_Aplikasi.bat
            (butuh Python 3.10+ terpasang, centang "Add Python to PATH" saat instal)
  Manual  : pip install -r requirements.txt
            streamlit run app.py
  Browser akan terbuka di http://localhost:8501

LANGKAH 3 - Pakai
  1. Unggah satu atau banyak file Excel/CSV dari mesin UTM.
  2. Atur di sidebar: interval, mulai (0,0), titik potong patah, satuan, desimal.
  3. Lihat grafik gabungan / per spesimen, lalu unduh Excel, PNG, atau ZIP semua hasil.

AGAR BISA DIPAKAI SEMUA KARYAWAN (opsional)
  Unggah folder ini (termasuk model/) ke GitHub, lalu deploy gratis di
  https://share.streamlit.io  -> pilih repo, file utama: app.py

CATATAN
  - Kalau muncul error saat memuat model, samakan versi library dengan Colab:
    di Colab jalankan  import lightgbm, sklearn; print(lightgbm.__version__, sklearn.__version__)
    lalu di komputer:  pip install lightgbm==<versi> scikit-learn==<versi>
  - Model baru (hasil latih ulang dengan data lebih banyak) cukup ditimpa ke folder model/,
    atau diunggah lewat sidebar aplikasi.
