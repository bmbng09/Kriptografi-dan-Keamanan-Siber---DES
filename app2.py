from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timedelta, time as dt_time
import csv
import os
from des import generate_subkeys, des_encrypt, des_decrypt
import mysql.connector

key = '0011000100110010001100110011010000110101001101100011011100111000'
subkeys = generate_subkeys(key)

# Koneksi ke MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="sistem_absensi_iot"
)
cursor = db.cursor()


app = Flask(__name__)

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Dashboard Absensi</title>
        <script src="https://cdn.jsdelivr.net/npm/sweetalert2@11"></script>
        <style>
            body {
                font-family: 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #84fab0, #8fd3f4);
                padding: 30px;
                margin: 0;
            }
            .container {
                max-width: 1000px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 16px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            }
            h2 {
                text-align: center;
                color: #333;
                margin-bottom: 10px;
            }
            .stats {
                display: flex;
                justify-content: space-between;
                margin-bottom: 20px;
            }
            .stat-box {
                background: #f1f1f1;
                padding: 15px 20px;
                border-radius: 12px;
                text-align: center;
                flex: 1;
                margin: 0 10px;
            }
            input[type="text"] {
                width: 100%;
                padding: 10px;
                border-radius: 8px;
                border: 1px solid #ccc;
                margin-bottom: 20px;
                font-size: 15px;
            }
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 12px;
                border-bottom: 1px solid #ddd;
                text-align: center;
            }
            th {
                background-color: #2c3e50;
                color: white;
            }
        </style>
        <script>
            let allData = [];

            function fetchData() {
                fetch('/data')
                    .then(response => response.json())
                    .then(data => {
                        if (data.alert) {
                            Swal.fire({
                                icon: 'info',
                                title: '⏳ Masih jam sekolah',
                                text: data.alert
                            });
                            return;
                        }
                        allData = data;
                        updateTable(data);
                        updateStats(data);
                    });
            }

            function updateTable(data) {
                const filter = document.getElementById('searchInput').value.toLowerCase();
                const tbody = document.getElementById('absensi-body');
                tbody.innerHTML = '';
                let no = 1;
                data.forEach(row => {
                    if (row[2].toLowerCase().includes(filter)) {
                        const waktu = row[0].split(' ');
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>${no++}</td>
                            <td>${row[2]}</td>
                            <td>${waktu[0]}</td>
                            <td>${waktu[1]}</td>
                            <td>${row[1]}</td>
                        `;
                        tbody.appendChild(tr);
                    }
                });
            }

            function updateStats(data) {
                const uids = new Set();
                let masuk = 0, keluar = 0;
                data.forEach(row => {
                    uids.add(row[1]);
                    if (row[3].includes('Absen masuk') || row[3].includes('Terlambat')) masuk++;
                    else if (row[3].includes('Absen keluar')) keluar++;
                });
                document.getElementById('totalSiswa').innerText = uids.size;
                document.getElementById('totalMasuk').innerText = masuk;
                document.getElementById('totalKeluar').innerText = keluar;
            }

            setInterval(fetchData, 1000);
            window.onload = fetchData;
        </script>
    </head>
    <body>
        <div class="container">
            <h2>📚 Sistem Absensi Siswa</h2>
            <div class="stats">
                <div class="stat-box">👥 Total Siswa<br><strong id="totalSiswa">0</strong></div>
                <div class="stat-box">✅ Total Masuk<br><strong id="totalMasuk">0</strong></div>
                <div class="stat-box">🔁 Total Keluar<br><strong id="totalKeluar">0</strong></div>
            </div>
            <input type="text" id="searchInput" placeholder="Cari nama siswa..." oninput="updateTable(allData)">
            <table>
                <thead>
                    <tr>
                        <th>No</th>
                        <th>Nama Siswa</th>
                        <th>Hari, Tanggal</th>
                        <th>Pukul</th>
                        <th>UID</th>
                    </tr>
                </thead>
                <tbody id="absensi-body"></tbody>
            </table>
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/absen', methods=['POST'])
def absen():
    data = request.get_json()
    uid = data.get('uid', 'unknown')
    nama = data.get('nama', 'unknown')
    now = datetime.now()
    unix_timestamp = int(now.timestamp())  # ini menghasilkan seperti: 1751962800
    timestamp_bin = bin(unix_timestamp)[2:].zfill(64)
    timestamp_encrypted = des_encrypt(timestamp_bin, subkeys)



    jam_masuk_awal = dt_time(12, 00)
    jam_masuk_batas = dt_time(12, 10)
    jam_pulang = dt_time(15, 30)

    # Cek apakah user sudah tap baru-baru ini (kurang dari 60 detik)
    cursor.execute("SELECT waktu FROM kripto WHERE uid = %s ORDER BY waktu DESC LIMIT 1", (uid,))
    last_tap = cursor.fetchone()
    if last_tap:
        last_encrypted = last_tap[0]
        last_bin = des_decrypt(last_encrypted, subkeys)
        last_unix = int(last_bin, 2)
        last_time = datetime.fromtimestamp(last_unix)
        if (now - last_time).total_seconds() < 60:
            return jsonify({"alert": "Silakan tunggu sebentar sebelum tap lagi"}), 200


    # Simpan ke database
    query = "INSERT INTO kripto (uid, nama, waktu) VALUES (%s, %s, %s)"
    val = (uid, nama, timestamp_encrypted)
    cursor.execute(query, val)
    db.commit()

    # Simpan ke file CSV juga
    with open('kripto.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([now.strftime('%Y-%m-%d %H:%M:%S'), uid, nama, timestamp_encrypted])

    return "OK", 200


@app.route('/data')
def data():
    try:
        data_list = []

        # Ambil dari MySQL
        cursor.execute("SELECT waktu, uid, nama FROM kripto ORDER BY waktu DESC")
        results = cursor.fetchall()

        for row in results:
            waktu_encrypted = row[0]
            uid = row[1]
            nama = row[2]

            # DES dekripsi
            plain_bin = des_decrypt(waktu_encrypted, subkeys)
            unix_timestamp = int(plain_bin, 2)
            waktu_obj = datetime.fromtimestamp(unix_timestamp)
            waktu_str = waktu_obj.strftime('%Y-%m-%d %H:%M:%S')

            data_list.append([waktu_str, uid, nama])

        return jsonify(data_list)
    except Exception as e:
        print("❌ Error saat mengambil data:", e)
        return jsonify({"error": "Gagal mengambil data", "detail": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050)