# -*- coding: utf-8 -*-
"""
Generator laporan DOCX (OOXML) tanpa dependensi eksternal.
Membangun file .docx (ZIP berisi XML) langsung dari Python standard library.

Menghasilkan: Laporan_Tugas_Besar_Jarkom_Kelompok-9.docx
"""
import os
import zipfile
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "Laporan_Tugas_Besar_Jarkom_Kelompok-9.docx")


# --------------------------------------------------------------------------
# Helper escaping
# --------------------------------------------------------------------------
def esc(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


# --------------------------------------------------------------------------
# Builder paragraf / heading / tabel
# --------------------------------------------------------------------------
def para(text="", style=None, bold=False, italic=False, size=None,
         align=None, color=None, spacing_after=120):
    """Satu paragraf teks biasa."""
    ppr = ['<w:spacing w:after="%d"/>' % spacing_after]
    if style:
        ppr.insert(0, '<w:pStyle w:val="%s"/>' % style)
    if align:
        ppr.append('<w:jc w:val="%s"/>' % align)
    rpr = []
    if bold:
        rpr.append('<w:b/>')
    if italic:
        rpr.append('<w:i/>')
    if size:
        rpr.append('<w:sz w:val="%d"/>' % (size * 2))
        rpr.append('<w:szCs w:val="%d"/>' % (size * 2))
    if color:
        rpr.append('<w:color w:val="%s"/>' % color)
    rpr_xml = '<w:rPr>%s</w:rPr>' % "".join(rpr) if rpr else ""
    return ('<w:p><w:pPr>%s</w:pPr>'
            '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % ("".join(ppr), rpr_xml, esc(text)))


def heading(text, level=1):
    style = "Heading%d" % level
    return ('<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (style, esc(text)))


def title_block(lines):
    """Beberapa baris judul besar, rata tengah."""
    out = []
    for i, (txt, sz, bold) in enumerate(lines):
        out.append(
            '<w:p><w:pPr><w:jc w:val="center"/>'
            '<w:spacing w:before="60" w:after="60"/></w:pPr>'
            '<w:r><w:rPr>%s<w:sz w:val="%d"/><w:szCs w:val="%d"/></w:rPr>'
            '<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % ('<w:b/>' if bold else "", sz * 2, sz * 2, esc(txt)))
    return "".join(out)


def page_break():
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def code_block(code_text):
    """Blok kode: tiap baris jadi paragraf style 'Code' (monospace)."""
    out = []
    lines = code_text.split("\n")
    for ln in lines:
        out.append(
            '<w:p><w:pPr><w:pStyle w:val="Code"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % esc(ln if ln else " "))
    return "".join(out)


def bullet(text):
    return ('<w:p><w:pPr><w:pStyle w:val="ListBullet"/>'
            '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
            '<w:spacing w:after="60"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % esc(text))


def _cell(text, bold=False, shade=None, width=2400):
    rpr = '<w:b/>' if bold else ""
    tcpr = '<w:tcW w:w="%d" w:type="dxa"/>' % width
    if shade:
        tcpr += '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % shade
    return ('<w:tc><w:tcPr>%s</w:tcPr>'
            '<w:p><w:pPr><w:spacing w:after="20"/></w:pPr>'
            '<w:r><w:rPr>%s</w:rPr>'
            '<w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
            % (tcpr, rpr, esc(text)))


def table(headers, rows, widths=None):
    if widths is None:
        widths = [int(9000 / len(headers))] * len(headers)
    border = ('<w:tblBorders>'
              '<w:top w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '<w:left w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '<w:right w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
              '</w:tblBorders>')
    out = ['<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/>%s'
           '<w:tblLook w:val="04A0"/></w:tblPr>' % border]
    # header row
    out.append('<w:tr>')
    for h, w in zip(headers, widths):
        out.append(_cell(h, bold=True, shade="D9E2F3", width=w))
    out.append('</w:tr>')
    # data rows
    for row in rows:
        out.append('<w:tr>')
        for c, w in zip(row, widths):
            out.append(_cell(c, width=w))
        out.append('</w:tr>')
    out.append('</w:tbl>')
    out.append(para("", spacing_after=120))
    return "".join(out)


def read_code(name):
    with open(os.path.join(BASE, name), "r", encoding="utf-8") as f:
        return f.read().rstrip("\n")


# --------------------------------------------------------------------------
# Susun isi dokumen
# --------------------------------------------------------------------------
def build_body():
    today = datetime.date.today().strftime("%d %B %Y")
    b = []

    # ---------- COVER ----------
    b.append(para("", spacing_after=400))
    b.append(title_block([
        ("LAPORAN TUGAS BESAR", 20, True),
        ("JARINGAN KOMPUTER - MODUL 8", 18, True),
    ]))
    b.append(para("", spacing_after=200))
    b.append(title_block([
        ("Implementasi Sistem Client - Proxy - Server", 16, True),
        ("Berbasis Socket Python (TCP & UDP)", 14, True),
    ]))
    b.append(para("", spacing_after=600))
    b.append(title_block([
        ("Disusun oleh:", 12, False),
        ("Kelompok 9", 14, True),
        ("[NIM] - [NAMA]", 12, False),
    ]))
    b.append(para("", spacing_after=600))
    b.append(title_block([
        ("Laboratorium Praktikum Informatika", 12, False),
        ("Fakultas Informatika", 12, False),
        ("UNIVERSITAS TELKOM", 14, True),
        (today, 11, False),
    ]))
    b.append(page_break())

    # ---------- DAFTAR ISI (ringkas) ----------
    b.append(heading("Daftar Isi", 1))
    toc = [
        "A. Pendahuluan",
        "B. Topologi dan Arsitektur Sistem",
        "C. Konfigurasi Port",
        "D. Implementasi Web Server (webserver.py)",
        "E. Implementasi Proxy Server (proxy.py)",
        "F. Implementasi Client (client.py)",
        "G. Halaman Uji (index.html)",
        "H. Skenario Pengujian dan Analisis QoS",
        "I. Kesimpulan",
    ]
    for t in toc:
        b.append(para(t, spacing_after=60))
    b.append(page_break())

    # ---------- A. PENDAHULUAN ----------
    b.append(heading("A. Pendahuluan", 1))
    b.append(heading("A.1 Latar Belakang", 2))
    b.append(para(
        "Tugas besar ini mengimplementasikan sebuah sistem jaringan sederhana "
        "yang terdiri atas tiga komponen utama, yaitu Web Server, Proxy Server, "
        "dan Client. Seluruh komponen dibangun menggunakan pemrograman socket "
        "pada bahasa Python dengan memanfaatkan dua protokol transport: TCP untuk "
        "layanan HTTP dan UDP untuk pengukuran Quality of Service (QoS). "
        "Sistem dirancang agar Web Server hanya dapat diakses melalui Proxy, "
        "sehingga Proxy berperan sebagai perantara sekaligus mekanisme caching."))
    b.append(heading("A.2 Tujuan", 2))
    b.append(bullet("Memahami komunikasi socket TCP dan UDP pada model Client-Proxy-Server."))
    b.append(bullet("Menerapkan multithreading agar server dan proxy dapat melayani banyak client secara bersamaan."))
    b.append(bullet("Menerapkan mekanisme caching pada Proxy untuk mempercepat respons."))
    b.append(bullet("Mengukur dan menganalisis parameter QoS: RTT, jitter, packet loss, dan throughput."))
    b.append(bullet("Menyimpan hasil pengukuran QoS ke berkas CSV untuk keperluan analisis."))

    # ---------- B. TOPOLOGI ----------
    b.append(heading("B. Topologi dan Arsitektur Sistem", 1))
    b.append(para(
        "Alur komunikasi sistem mengikuti pola berikut. Browser atau Client "
        "tidak diizinkan mengakses Web Server secara langsung; seluruh permintaan "
        "HTTP harus melewati Proxy Server."))
    b.append(para("Client / Browser  -->  Proxy Server (TCP 8080)  -->  Web Server (TCP 8000)",
                  style="Code"))
    b.append(para(
        "Untuk pengukuran QoS, Client mengirimkan paket UDP langsung ke modul "
        "Echo Server pada Web Server (UDP 9090) dan mengukur waktu pulang-pergi "
        "(round-trip time) tiap paket."))
    b.append(para("Client (UDP)  -->  Web Server Echo (UDP 9090)  -->  Client (UDP)",
                  style="Code"))
    b.append(heading("B.1 Peran Tiap Komponen", 2))
    b.append(bullet("Web Server: melayani permintaan HTTP GET (TCP) dan memantulkan paket UDP (echo). Hanya menerima koneksi TCP dari IP Proxy."))
    b.append(bullet("Proxy Server: menerima permintaan dari Client, mengecek cache, meneruskan ke Web Server bila cache miss, lalu menyimpan respons 200 OK ke cache."))
    b.append(bullet("Client: mengirim HTTP GET via Proxy serta melakukan UDP QoS Ping Test, dilengkapi menu interaktif."))

    # ---------- C. KONFIGURASI PORT ----------
    b.append(heading("C. Konfigurasi Port", 1))
    b.append(table(
        ["Komponen", "Protokol", "Port"],
        [
            ["Web Server (HTTP)", "TCP", "8000"],
            ["Web Server (UDP Echo)", "UDP", "9090"],
            ["Proxy Server", "TCP", "8080"],
            ["Client", "TCP / UDP", "Ephemeral"],
        ],
        widths=[4000, 2500, 2500]))
    b.append(para(
        "Port UDP menggunakan 9090 untuk menghindari konflik dengan layanan lain "
        "yang umum memakai port 9000.", italic=True))

    # ---------- D. WEB SERVER ----------
    b.append(heading("D. Implementasi Web Server (webserver.py)", 1))
    b.append(para(
        "Web Server menjalankan dua thread utama: thread TCP untuk HTTP dan "
        "thread UDP untuk echo. Setiap koneksi TCP ditangani pada thread terpisah "
        "dengan nama deskriptif (TCP-<ip>-<port>) sehingga konkurensi tercatat "
        "jelas pada log. Web Server juga memvalidasi IP sumber: hanya koneksi dari "
        "Proxy yang diterima, selain itu akan dibalas dengan 403 Forbidden."))
    b.append(heading("D.1 Fitur Utama", 2))
    b.append(bullet("Multithreading eksplisit untuk TCP dan UDP (thread bernama)."))
    b.append(bullet("Pembatasan akses: hanya IP Proxy (127.0.0.1) yang boleh mengakses langsung."))
    b.append(bullet("Penanganan HTTP 200 OK dan 404 Not Found."))
    b.append(bullet("UDP Echo Server pada port 9090 dengan thread per-datagram."))
    b.append(heading("D.2 Kode Sumber", 2))
    b.append(code_block(read_code("webserver.py")))
    b.append(page_break())

    # ---------- E. PROXY SERVER ----------
    b.append(heading("E. Implementasi Proxy Server (proxy.py)", 1))
    b.append(para(
        "Proxy Server menerima koneksi dari Client dan menanganinya pada thread "
        "terpisah bernama Proxy-<ip>-<port>. Proxy melakukan pengecekan cache "
        "dengan sinkronisasi lock agar thread-safe. Bila respons tersedia di cache "
        "(Cache HIT) maka langsung dikirim ke Client; bila tidak (Cache MISS), "
        "permintaan diteruskan ke Web Server dan respons 200 OK disimpan ke cache."))
    b.append(heading("E.1 Penanganan Error", 2))
    b.append(para(
        "Proxy diperkuat dengan penanganan error yang lengkap sehingga tidak crash "
        "ketika menerima request rusak atau ketika server tujuan bermasalah."))
    b.append(table(
        ["Kondisi", "Kode HTTP", "Keterangan"],
        [
            ["Request tidak valid (malformed)", "400 Bad Request", "Baris HTTP tidak dapat diurai"],
            ["Server tidak bisa dihubungi", "502 Bad Gateway", "ConnectionRefusedError / Reset"],
            ["Server tidak merespons", "504 Gateway Timeout", "socket.timeout"],
            ["Error socket umum", "503 Service Unavailable", "socket.error lainnya"],
            ["Cache gagal dibaca/ditulis", "Log warning, lanjut", "IOError ditangani"],
            ["Client disconnect tiba-tiba", "Log warning, berhenti", "BrokenPipe / ConnectionReset"],
        ],
        widths=[3400, 2600, 3000]))
    b.append(heading("E.2 Kode Sumber", 2))
    b.append(code_block(read_code("proxy.py")))
    b.append(page_break())

    # ---------- F. CLIENT ----------
    b.append(heading("F. Implementasi Client (client.py)", 1))
    b.append(para(
        "Client menyediakan menu interaktif saat dijalankan tanpa argumen, dan "
        "tetap mendukung argumen CLI (--mode tcp|udp) untuk pengujian otomatis. "
        "Fungsi tcp_client mengirim HTTP GET melalui Proxy, sedangkan udp_pinger "
        "melakukan UDP QoS Ping Test dan menyimpan hasilnya ke berkas qos_log.csv."))
    b.append(heading("F.1 Menu Interaktif", 2))
    b.append(bullet("[1] HTTP GET via Proxy (TCP) untuk /index.html"))
    b.append(bullet("[2] UDP QoS Ping Test ke server"))
    b.append(bullet("[3] HTTP GET resource tertentu via Proxy"))
    b.append(bullet("[0] Keluar"))
    b.append(heading("F.2 Parameter QoS yang Diukur", 2))
    b.append(bullet("RTT (Round-Trip Time): min, rata-rata, dan maksimum dalam milidetik."))
    b.append(bullet("Jitter: standar deviasi dari selisih RTT antar paket berurutan."))
    b.append(bullet("Packet Loss: persentase paket yang timeout terhadap total paket."))
    b.append(bullet("Throughput: total bit diterima dibagi durasi pengujian (kbps)."))
    b.append(heading("F.3 Format Berkas CSV (qos_log.csv)", 2))
    b.append(para(
        "session_start, seq, status, rtt_ms, bytes_received", style="Code"))
    b.append(para(
        "Baris terakhir tiap sesi berisi ringkasan (SUMMARY) yang memuat packet "
        "loss, jitter, throughput, serta RTT min/avg/max."))
    b.append(heading("F.4 Kode Sumber", 2))
    b.append(code_block(read_code("client.py")))
    b.append(page_break())

    # ---------- G. INDEX.HTML ----------
    b.append(heading("G. Halaman Uji (index.html)", 1))
    b.append(para(
        "Halaman HTML sederhana yang dilayani oleh Web Server sebagai konten uji "
        "ketika Client melakukan HTTP GET melalui Proxy."))
    b.append(code_block(read_code("index.html")))

    # ---------- H. PENGUJIAN ----------
    b.append(heading("H. Skenario Pengujian dan Analisis QoS", 1))
    b.append(heading("H.1 Langkah Pengujian", 2))
    b.append(bullet("Jalankan Web Server: python webserver.py"))
    b.append(bullet("Jalankan Proxy Server: python proxy.py"))
    b.append(bullet("Jalankan Client: python client.py (menu interaktif)"))
    b.append(bullet("Pilih menu [1] untuk menguji HTTP GET via Proxy (amati Cache MISS lalu Cache HIT pada permintaan kedua)."))
    b.append(bullet("Pilih menu [2] untuk menjalankan UDP QoS Ping Test dan menghasilkan qos_log.csv."))
    b.append(bullet("Verifikasi browser diarahkan ke http://127.0.0.1:8080/index.html (alamat Proxy), bukan port 8000."))
    b.append(heading("H.2 Contoh Tabel Hasil QoS", 2))
    b.append(para(
        "Tabel berikut adalah format hasil pengukuran yang dapat diisi setelah "
        "pengujian dilakukan (nilai bersifat ilustratif)."))
    b.append(table(
        ["Parameter", "Nilai", "Satuan"],
        [
            ["RTT Minimum", "...", "ms"],
            ["RTT Rata-rata", "...", "ms"],
            ["RTT Maksimum", "...", "ms"],
            ["Jitter", "...", "ms"],
            ["Packet Loss", "...", "%"],
            ["Throughput", "...", "kbps"],
        ],
        widths=[4000, 2500, 2500]))
    b.append(heading("H.3 Analisis", 2))
    b.append(para(
        "Pada permintaan HTTP pertama, Proxy mengalami Cache MISS karena harus "
        "meneruskan permintaan ke Web Server, sehingga waktu respons lebih besar. "
        "Pada permintaan berikutnya untuk resource yang sama, Proxy mengalami "
        "Cache HIT dan melayani langsung dari cache sehingga waktu respons jauh "
        "lebih kecil. Hal ini membuktikan efektivitas mekanisme caching."))
    b.append(para(
        "Untuk QoS UDP, nilai packet loss yang rendah dan jitter yang kecil "
        "menunjukkan kualitas jaringan lokal yang stabil. RTT pada localhost "
        "umumnya sangat kecil karena tidak melalui jaringan fisik."))

    # ---------- I. KESIMPULAN ----------
    b.append(heading("I. Kesimpulan", 1))
    b.append(bullet("Sistem Client-Proxy-Server berhasil diimplementasikan menggunakan socket TCP dan UDP pada Python."))
    b.append(bullet("Multithreading memungkinkan server dan proxy melayani banyak client secara bersamaan, dibuktikan melalui nama thread pada log."))
    b.append(bullet("Mekanisme caching pada Proxy terbukti mempercepat respons (Cache HIT lebih cepat daripada Cache MISS)."))
    b.append(bullet("Web Server hanya dapat diakses melalui Proxy karena adanya validasi IP sumber (403 Forbidden untuk akses langsung)."))
    b.append(bullet("Pengukuran QoS (RTT, jitter, packet loss, throughput) berhasil dilakukan dan disimpan ke berkas qos_log.csv."))
    b.append(bullet("Penanganan error pada Proxy (400/502/503/504, IOError, BrokenPipe) membuat sistem lebih tangguh."))

    return "".join(b)


# --------------------------------------------------------------------------
# Bagian XML statik
# --------------------------------------------------------------------------
CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>'''

RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOC_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>'''

NUMBERING = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:abstractNum w:abstractNumId="0">
    <w:lvl w:ilvl="0">
      <w:start w:val="1"/>
      <w:numFmt w:val="bullet"/>
      <w:lvlText w:val="&#8226;"/>
      <w:lvlJc w:val="left"/>
      <w:pPr><w:ind w:left="540" w:hanging="270"/></w:pPr>
      <w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr>
    </w:lvl>
  </w:abstractNum>
  <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>
</w:numbering>'''

STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault><w:rPr>
      <w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/>
      <w:sz w:val="22"/><w:szCs w:val="22"/>
    </w:rPr></w:rPrDefault>
  </w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
    <w:name w:val="Normal"/>
    <w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="280" w:after="120"/><w:outlineLvl w:val="0"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="30"/><w:szCs w:val="30"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:keepNext/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="1"/><w:jc w:val="left"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="2E5496"/><w:sz w:val="26"/><w:szCs w:val="26"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Code">
    <w:name w:val="Code"/><w:basedOn w:val="Normal"/>
    <w:pPr>
      <w:spacing w:after="0" w:line="240" w:lineRule="auto"/>
      <w:jc w:val="left"/>
      <w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>
      <w:ind w:left="120"/>
    </w:pPr>
    <w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/><w:sz w:val="17"/><w:szCs w:val="17"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="ListBullet">
    <w:name w:val="List Bullet"/><w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:after="60"/><w:jc w:val="left"/></w:pPr>
  </w:style>
</w:styles>'''


def document_xml():
    body = build_body()
    sect = ('<w:sectPr>'
            '<w:pgSz w:w="11906" w:h="16838"/>'
            '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
            'w:header="708" w:footer="708" w:gutter="0"/>'
            '</w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>%s%s</w:body></w:document>' % (body, sect))


def main():
    doc = document_xml()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", STYLES)
        z.writestr("word/numbering.xml", NUMBERING)
    print("[OK] Laporan dibuat:", OUT)
    print("     Ukuran:", os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
