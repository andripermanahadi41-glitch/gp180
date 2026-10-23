# GP180 Studio — catatan porting (WORK IN PROGRESS)

Basis: GP200 Studio (editor Python untuk Valeton GP-200).
Firmware acuan: GP-180 Firmware V1.0.0 (rilis 26/03/2026, terbaca jelas).
Firmware V1.1.1 (rilis 20/08/2026: latensi ganti patch/CTRL lebih rendah, dukungan NAM A2 Lite/konversi) sudah diperiksa tetapi **terkompresi** (5 MB; bukan LZ4/LZF/FastLZ/zlib/lzma), jadi tabelnya belum bisa dibaca. Data `data/gp180_fw/` tetap dari V1.0.0. Editor resmi v2.1.0 BELUM dipakai.

## Sudah dikerjakan
1. **Rebranding**: semua file/teks `GP200` → `GP180` (kode, UI, i18n, build, panduan). `CHANGELOG.md` sengaja tidak diubah (riwayat GP200).
2. **Pengaman**: `gp180_device.py` + guard di `gp180_usb.py`. Pengiriman SysEx ke pedal **diblokir** selama `PROTOCOL_VERIFIED = False`.
3. **Konstanta spesifikasi GP-180** terpusat di `gp180_device.py` (12 modul, 200 slot, 100 preset pabrik, 50/100 SnapTone, 20 slot IR, looper 180 dtk).
4. **Ekstraksi firmware** (`tools/extract_fw.py` → `data/gp180_fw/`):
   - `snaptone_factory.json` — 50 nama SnapTone pabrik + 50 slot user kosong. **Andal** (tabel jelas, ada 2 salinan identik).
   - `models_draft.json` — 71 deskriptor model + parameter (min/max/step/default/slot/tipe). **Kepercayaan rendah**: baru sebagian model terdeteksi (perkiraan 200+ total), label kategori dan urutan nama parameter belum pasti, dan `model_id`/`category` belum ditemukan.
   - `usb_strings.json` — nama perangkat ("GP-180 Audio", "GP-180 BLE", RMT_MIDI).

## Belum bisa / sengaja tidak diubah
- **Format `.prst` (1224 byte, 11 modul)**, `N_MODULES`, `MODULES` di `gp180lib.py`: masih format GP-200. Format GP-180 (12 modul) belum diketahui, jadi tidak ditebak.
- **Protokol SysEx**, `GP180_VID/PID`, ID SysEx `F0 21 25 7E 47 50 2D 32`: nilai GP-200, **tidak ditemukan** di firmware GP-180 → perlu capture USB/MIDI nyata.
- **Skema bank/preset** (GP-200: 32 bank × A–D = 128). GP-180 punya 200 slot; pemetaan program change belum diketahui. Masih `slot_to_pc` GP-200 di `gp180_usb.py`/`gp180_midi.py`/`gp180_batch.py`.
- `data/*.json` (model, preset pabrik, deskripsi, cab) masih data **GP-200**; `gp180_studio.py` masih meng-assert 128 preset pabrik.

## Langkah berikut yang paling efektif
1. Unduh **Software komputer GP-180 v2.1.0** (editor resmi) dan unggah folder instalasinya: biasanya memuat tabel model/parameter/deskripsi (seperti `algorithm.xml` yang dipakai di GP200 Studio).
2. Atau capture USB (Wireshark+USBPcap) saat editor resmi membaca/menulis satu preset.
3. Setelah cocok: ganti `data/`, `MODULES/N_MODULES/FILE_SIZE`, ID SysEx, bank→PC; lalu set `PROTOCOL_VERIFIED = True`.

## Update: Valeton Suite V2.1.0 (installer Windows) sudah dibongkar
Installer NSIS (deflate per file); aplikasinya Flutter (`qme10_pc`) dengan kode Dart AOT (`app.so`).
- **Katalog GP-180 resmi**: `data/gp180_suite/module_data.json` (12 modul: PRE, WAH, DST, N->S, AMP, NR, CAB, EQ, MOD, DLY, RVB, VOL; 348 entri = 226 efek + 122 N->S). Cocok 49/50 dengan nama SnapTone di firmware GP-180.
- Dikonversi ke format proyek: `data/gp180_models_suite.json` (`tools/build_catalog_from_suite.py`). 181 entri identik id/kategori dengan katalog GP-200 (konvensi `fxid = (cat<<24)|id` sama), 167 entri baru. `unit_code` baru terisi bila model+parameter sama dengan GP-200, selain itu 0 (belum diketahui). Ada juga deskripsi EN/CN dan asal efek.
- **Belum dipasang sebagai katalog aktif**: `gp180lib.py` masih membaca `gp180_models_all.json` (GP-200), karena penulis `.prst` dan protokol masih format GP-200. Mengganti katalog tanpa format baru akan menghasilkan file salah.
- Nama port MIDI resmi: **"Valeton GP-180 MIDI"** (dan "Valeton GP-180 Subdevice"); pencarian port `GP-180` di `gp180_usb.py` sudah cocok.
- Suite memakai kelas bernama `HT150...` / `Import150PresetResult` / `HTFirmwareHead` untuk GP-150/GP-180: kemungkinan GP-180 satu keluarga protokol dengan GP-150 (dugaan, belum terbukti).
- Protokol SysEx **tidak terbaca** dari Suite (ada di kode Dart AOT, bukan string). Yang masih dibutuhkan: capture USB/MIDI saat Suite membaca satu preset, atau dekompilasi `app.so`.
