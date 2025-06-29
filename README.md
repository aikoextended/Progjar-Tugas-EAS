
# 🏁 Checkers Multiplayer

## Development Team
| Name                      | NRP         |
|---------------------------|-------------|
| Decya Giovanni            | 5025221027  |
| Karina Rahmawati          | 5025221041  |
| Audrey Sasqhia Wijaya     | 5025221055  |
| Putri Meyliya Rachmawati  | 5025221062  |
| Lathifah Sahda            | 5025221159  |


## 📌 Deskripsi

**Checkers Multiplayer** adalah game Checkers (Dam) berbasis TCP/IP dengan arsitektur client-server yang memungkinkan **dua pemain bermain melalui jaringan**. Game ini dibangun menggunakan **Python** dengan **Pygame** untuk antarmuka grafis.

---

## ⚙️ Requierment

- **Python 3.x** sudah terinstal di perangkat Anda.
- Pustaka Python yang dibutuhkan:
  - [`pygame`](https://www.pygame.org/news)
  - Pustaka standar Python: `socket`, `json`, `threading`, `uuid`, `time`, `queue`, `copy`, `enum`.

### 📦 Cara Instalasi Dependensi

Jalankan perintah berikut di terminal:

```bash
pip install pygame
```

---

## 💻 Platform yang Didukung

- Windows
- Linux (Ubuntu)

---

## 🚀 Langkah-langkah Menjalankan Game

### 1. Menjalankan Server

1. Buka **terminal** atau **command prompt**.
2. Navigasikan ke direktori tempat file `server_thread_pool_http.py` dan `http_server.py` berada.
3. Jalankan server dengan perintah berikut:

   ```bash
   python server_thread_pool_http.py
   ```

   - Server akan berjalan pada port **8080** dengan alamat IP default **localhost**.

---

### 2. Menjalankan Client

1. Buka terminal baru (**atau pada perangkat lain** jika bermain melalui jaringan).
2. Navigasikan ke direktori tempat file `client.py` berada.
3. Jalankan client dengan perintah berikut:

   ```bash
   python client.py [server_host] [server_port]
   ```

   Ganti:
   - `[server_host]` dengan alamat IP server (contoh: `localhost` jika server berjalan di perangkat yang sama).
   - `[server_port]` dengan `8080`.

4. Jalankan client kedua dengan cara yang sama untuk pemain lawan.

> **Catatan:** Pastikan semua perangkat terhubung ke **jaringan yang sama** jika bermain melalui perangkat berbeda.

---

## 🎮 Cara Bermain

 **Bergabung ke Permainan**
- Setelah client dijalankan, pemain akan otomatis bergabung ke permainan dan menunggu lawan terhubung.
- Server akan memberikan `player_id` dan `game_id` sebagai identitas unik.

 **Giliran Bermain**
- Permainan bersifat **turn-based**, pemain bermain secara bergantian.
- Antarmuka akan menampilkan pesan **"YOUR TURN"** saat giliran pemain.

 **Gerakan Bidak**
- Klik bidak yang ingin dipindahkan (bidak valid akan disorot).
- Klik kotak tujuan yang valid (akan ditandai dengan warna hijau).
- Jika bidak lawan dapat dilompati, bidak tersebut akan dieliminasi.

 **King**
- Jika bidak mencapai ujung papan lawan, bidak akan menjadi **"king"** dan dapat bergerak maju maupun mundur.

 **Menang/Kalah**
- Pemain yang berhasil menghabiskan semua bidak lawan akan menang.
- Pesan **"YOU WIN!"** atau **"YOU LOSE"** akan muncul di akhir permainan.

 **Restart Game**
- Setelah permainan selesai, klik tombol **"RESTART GAME"** untuk memulai ulang permainan.
- Permainan hanya akan di-restart jika **kedua pemain menyetujui**.
