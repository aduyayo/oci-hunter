# OCI Auto-Hunter Cloud (Batam ap-batam-1)

Automated Oracle Cloud Infrastructure (OCI) Always Free ARM instance hunter running 24/7 via GitHub Actions.

## Setup Instructions

1. Buat repository baru di GitHub (Bisa **Public** atau **Private**).
   - *Tips:* Jika menggunakan repo **Public**, kuota GitHub Actions adalah **UNLIMITED (Tanpa Batas Menit)**! Dan tenang saja, kunci private key dan konfigurasi akun Anda tetap 100% aman karena tersimpan di **GitHub Secrets** (tidak akan terlihat oleh publik).
2. Tambahkan Repository Secrets di menu:
   `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
   (Daftar lengkap rahasia/secret sudah disiapkan di file `D:\Projek\Oracle\github_secrets.txt`).
3. Push folder ini ke repository GitHub Anda:
   ```bash
   git remote add origin https://github.com/<USERNAME>/<REPO_NAME>.git
   git push -u origin main
   ```
4. Masuk ke tab **Actions** di GitHub, pilih **OCI Cloud Hunter Batam**, lalu klik **Run workflow**.
5. Selesai! Bot akan berburu secara otomatis di cloud 24/7 dan mengirimkan notifikasi ke Telegram `@Aceelbot` begitu server sukses dibuat.
