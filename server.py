"""
MedStock ERP - Travmatologiya va ortopediya implantlari uchun
ombor, sotuv va qaytarish tizimi.

Texnologiya: Flask + SQLite (qo'shimcha og'ir o'rnatishlarsiz ishlaydi).
Ishga tushirish:
    pip install -r requirements.txt
    python server.py
    Brauzerda: http://localhost:5000
    Standart login:  admin / admin123
"""

from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import sqlite3
import os
import hmac
import hashlib
import base64
import json
import csv
import io
from datetime import datetime, date
from functools import wraps

try:
    from openpyxl import Workbook
    HAS_XLSX = True
except ImportError:
    HAS_XLSX = False

app = Flask(__name__)
CORS(app)

DB = 'ombor.db'
SECRET = os.environ.get('MEDSTOCK_SECRET', 'medstock-erp-secret-key-change-me')


# ----------------------------------------------------------------------------
# Baza
# ----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def today_str():
    return date.today().strftime("%Y-%m-%d")


def init_db():
    conn = get_db()
    c = conn.cursor()

    # Foydalanuvchilar
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT DEFAULT '',
        role TEXT DEFAULT 'menejer',
        created_at TEXT
    )''')

    # Mahsulotlar bazasi (Источник)
    c.execute('''CREATE TABLE IF NOT EXISTS mahsulotlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kod TEXT DEFAULT '',
        artikul TEXT DEFAULT '',
        nomi TEXT NOT NULL,
        birlik TEXT DEFAULT 'dona',
        qoldiq INTEGER DEFAULT 0,
        tannarx REAL DEFAULT 0,
        sotuv_narx REAL DEFAULT 0,
        sotilgan INTEGER DEFAULT 0,
        qaytarilgan INTEGER DEFAULT 0,
        created_at TEXT
    )''')

    # Kontragentlar bazasi (Источник2)
    c.execute('''CREATE TABLE IF NOT EXISTS kontragentlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        menejer TEXT DEFAULT '',
        status TEXT DEFAULT 'Aktiv',
        sklad TEXT DEFAULT '',
        telefon TEXT DEFAULT '',
        izoh TEXT DEFAULT ''
    )''')

    # Skladlar (omborlar)
    c.execute('''CREATE TABLE IF NOT EXISTS skladlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        manzil TEXT DEFAULT '',
        izoh TEXT DEFAULT ''
    )''')

    # Menejerlar (ro'yxat — dropdownlar uchun)
    c.execute('''CREATE TABLE IF NOT EXISTS menejerlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ism TEXT NOT NULL,
        telefon TEXT DEFAULT '',
        izoh TEXT DEFAULT ''
    )''')

    # Operatsiyalar moduli
    c.execute('''CREATE TABLE IF NOT EXISTS operatsiyalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sklad TEXT DEFAULT '',
        mahsulot_id INTEGER,
        otgr_kol INTEGER DEFAULT 0,
        vozvrat_kol INTEGER DEFAULT 0,
        prodaja INTEGER DEFAULT 0,
        sebest REAL DEFAULT 0,
        sotuv_narx REAL DEFAULT 0,
        summa_prodaj REAL DEFAULT 0,
        cost_summa REAL DEFAULT 0,
        zakaz_nomer TEXT DEFAULT '',
        status TEXT DEFAULT 'Отправлен',
        dogovor TEXT DEFAULT '',
        kontragent_id INTEGER,
        data_otgr TEXT DEFAULT '',
        data_prodaj TEXT DEFAULT '',
        menejer TEXT DEFAULT '',
        created_at TEXT,
        FOREIGN KEY (mahsulot_id) REFERENCES mahsulotlar(id),
        FOREIGN KEY (kontragent_id) REFERENCES kontragentlar(id)
    )''')

    # Audit log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        amal TEXT,
        obyekt TEXT,
        obyekt_id INTEGER,
        tafsilot TEXT,
        sana TEXT
    )''')

    conn.commit()

    # Standart admin
    row = c.execute("SELECT COUNT(*) n FROM users").fetchone()
    if row['n'] == 0:
        c.execute(
            "INSERT INTO users (username,password_hash,full_name,role,created_at) VALUES (?,?,?,?,?)",
            ('admin', hash_password('admin123'), 'Administrator', 'admin', now_str()))
        conn.commit()

    conn.close()


# ----------------------------------------------------------------------------
# Parol & JWT (tashqi kutubxonasiz HMAC token)
# ----------------------------------------------------------------------------
def hash_password(password):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return base64.b64encode(salt).decode() + '$' + base64.b64encode(dk).decode()


def verify_password(password, stored):
    try:
        salt_b64, dk_b64 = stored.split('$')
        salt = base64.b64decode(salt_b64)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return hmac.compare_digest(base64.b64encode(dk).decode(), dk_b64)
    except Exception:
        return False


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()


def b64url_dec(s):
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)


def make_token(payload):
    body = b64url(json.dumps(payload).encode())
    sig = b64url(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return body + '.' + sig


def read_token(token):
    try:
        body, sig = token.split('.')
        expected = b64url(hmac.new(SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        return json.loads(b64url_dec(body))
    except Exception:
        return None


def current_user():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return read_token(auth[7:])
    return None


def login_required(role=None):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                return jsonify({'error': 'Avtorizatsiya talab qilinadi'}), 401
            if role == 'admin' and u.get('role') != 'admin':
                return jsonify({'error': 'Faqat admin uchun'}), 403
            request.user = u
            return fn(*a, **kw)
        return wrapper
    return deco


def audit(username, amal, obyekt, obyekt_id=None, tafsilot=''):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (username,amal,obyekt,obyekt_id,tafsilot,sana) VALUES (?,?,?,?,?,?)",
        (username, amal, obyekt, obyekt_id, tafsilot, now_str()))
    conn.commit()
    conn.close()


# ----------------------------------------------------------------------------
# Auth endpointlari
# ----------------------------------------------------------------------------
@app.route('/api/login', methods=['POST'])
def login():
    d = request.json or {}
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=?", (d.get('username', ''),)).fetchone()
    conn.close()
    if not u or not verify_password(d.get('password', ''), u['password_hash']):
        return jsonify({'error': 'Login yoki parol xato'}), 401
    payload = {'id': u['id'], 'username': u['username'],
               'full_name': u['full_name'], 'role': u['role']}
    return jsonify({'token': make_token(payload), 'user': payload})


@app.route('/api/me', methods=['GET'])
@login_required()
def me():
    return jsonify(request.user)


@app.route('/api/users', methods=['GET'])
@login_required('admin')
def users_list():
    conn = get_db()
    rows = conn.execute(
        "SELECT id,username,full_name,role,created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/users', methods=['POST'])
@login_required('admin')
def user_add():
    d = request.json or {}
    if not d.get('username') or not d.get('password'):
        return jsonify({'error': 'Login va parol majburiy'}), 400
    conn = get_db()
    try:
        cur = conn.execute(
            "INSERT INTO users (username,password_hash,full_name,role,created_at) VALUES (?,?,?,?,?)",
            (d['username'], hash_password(d['password']), d.get('full_name', ''),
             d.get('role', 'menejer'), now_str()))
        conn.commit()
        uid = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Bunday login mavjud'}), 400
    conn.close()
    audit(request.user['username'], 'qoshdi', 'foydalanuvchi', uid, d['username'])
    return jsonify({'status': 'ok'})


@app.route('/api/users/<int:uid>', methods=['DELETE'])
@login_required('admin')
def user_del(uid):
    if uid == request.user['id']:
        return jsonify({'error': "O'zingizni o'chira olmaysiz"}), 400
    conn = get_db()
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'foydalanuvchi', uid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Mahsulotlar
# ----------------------------------------------------------------------------
def mahsulot_dict(r):
    d = dict(r)
    try:
        created = datetime.strptime((d.get('created_at') or '')[:10], "%Y-%m-%d").date()
        d['omborda_kunlar'] = (date.today() - created).days
    except Exception:
        d['omborda_kunlar'] = 0
    return d


@app.route('/api/mahsulotlar', methods=['GET'])
@login_required()
def mahsulotlar_list():
    q = request.args.get('q', '').strip().lower()
    conn = get_db()
    rows = conn.execute("SELECT * FROM mahsulotlar ORDER BY nomi").fetchall()
    conn.close()
    data = [mahsulot_dict(r) for r in rows]
    if q:
        data = [m for m in data if q in (m['nomi'] or '').lower()
                or q in (m['artikul'] or '').lower() or q in (m['kod'] or '').lower()]
    return jsonify(data)


@app.route('/api/mahsulotlar', methods=['POST'])
@login_required('admin')
def mahsulot_qosh():
    d = request.json or {}
    if not d.get('nomi'):
        return jsonify({'error': 'Nomi majburiy'}), 400
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO mahsulotlar (kod,artikul,nomi,birlik,qoldiq,tannarx,sotuv_narx,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (d.get('kod', ''), d.get('artikul', ''), d['nomi'], d.get('birlik', 'dona'),
         d.get('qoldiq', 0), d.get('tannarx', 0), d.get('sotuv_narx', 0), now_str()))
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    audit(request.user['username'], 'qoshdi', 'mahsulot', mid, d['nomi'])
    return jsonify({'status': 'ok', 'id': mid})


@app.route('/api/mahsulotlar/<int:mid>', methods=['PUT'])
@login_required('admin')
def mahsulot_yangilash(mid):
    d = request.json or {}
    conn = get_db()
    conn.execute(
        """UPDATE mahsulotlar SET kod=?,artikul=?,nomi=?,birlik=?,qoldiq=?,tannarx=?,sotuv_narx=?
           WHERE id=?""",
        (d.get('kod', ''), d.get('artikul', ''), d['nomi'], d.get('birlik', 'dona'),
         d.get('qoldiq', 0), d.get('tannarx', 0), d.get('sotuv_narx', 0), mid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'tahrirladi', 'mahsulot', mid, d.get('nomi', ''))
    return jsonify({'status': 'ok'})


@app.route('/api/mahsulotlar/<int:mid>', methods=['DELETE'])
@login_required('admin')
def mahsulot_ochir(mid):
    conn = get_db()
    conn.execute("DELETE FROM mahsulotlar WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'mahsulot', mid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Kontragentlar
# ----------------------------------------------------------------------------
@app.route('/api/kontragentlar', methods=['GET'])
@login_required()
def kontragentlar_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM kontragentlar ORDER BY nomi").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/kontragentlar', methods=['POST'])
@login_required()
def kontragent_qosh():
    d = request.json or {}
    if not d.get('nomi'):
        return jsonify({'error': 'Nomi majburiy'}), 400
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO kontragentlar (nomi,menejer,status,sklad,telefon,izoh) VALUES (?,?,?,?,?,?)",
        (d['nomi'], d.get('menejer', ''), d.get('status', 'Aktiv'),
         d.get('sklad', ''), d.get('telefon', ''), d.get('izoh', '')))
    conn.commit()
    kid = cur.lastrowid
    conn.close()
    audit(request.user['username'], 'qoshdi', 'kontragent', kid, d['nomi'])
    return jsonify({'status': 'ok', 'id': kid})


@app.route('/api/kontragentlar/<int:kid>', methods=['PUT'])
@login_required()
def kontragent_yangilash(kid):
    d = request.json or {}
    conn = get_db()
    conn.execute(
        "UPDATE kontragentlar SET nomi=?,menejer=?,status=?,sklad=?,telefon=?,izoh=? WHERE id=?",
        (d['nomi'], d.get('menejer', ''), d.get('status', 'Aktiv'),
         d.get('sklad', ''), d.get('telefon', ''), d.get('izoh', ''), kid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'tahrirladi', 'kontragent', kid, d.get('nomi', ''))
    return jsonify({'status': 'ok'})


@app.route('/api/kontragentlar/<int:kid>', methods=['DELETE'])
@login_required('admin')
def kontragent_ochir(kid):
    conn = get_db()
    conn.execute("DELETE FROM kontragentlar WHERE id=?", (kid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'kontragent', kid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Skladlar (omborlar)
# ----------------------------------------------------------------------------
@app.route('/api/skladlar', methods=['GET'])
@login_required()
def skladlar_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM skladlar ORDER BY nomi").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/skladlar', methods=['POST'])
@login_required('admin')
def sklad_qosh():
    d = request.json or {}
    if not d.get('nomi'):
        return jsonify({'error': 'Nomi majburiy'}), 400
    conn = get_db()
    cur = conn.execute("INSERT INTO skladlar (nomi,manzil,izoh) VALUES (?,?,?)",
                       (d['nomi'], d.get('manzil', ''), d.get('izoh', '')))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    audit(request.user['username'], 'qoshdi', 'sklad', sid, d['nomi'])
    return jsonify({'status': 'ok', 'id': sid})


@app.route('/api/skladlar/<int:sid>', methods=['PUT'])
@login_required('admin')
def sklad_yangilash(sid):
    d = request.json or {}
    conn = get_db()
    conn.execute("UPDATE skladlar SET nomi=?,manzil=?,izoh=? WHERE id=?",
                 (d['nomi'], d.get('manzil', ''), d.get('izoh', ''), sid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'tahrirladi', 'sklad', sid, d.get('nomi', ''))
    return jsonify({'status': 'ok'})


@app.route('/api/skladlar/<int:sid>', methods=['DELETE'])
@login_required('admin')
def sklad_ochir(sid):
    conn = get_db()
    conn.execute("DELETE FROM skladlar WHERE id=?", (sid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'sklad', sid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Menejerlar (ro'yxat)
# ----------------------------------------------------------------------------
@app.route('/api/menejerlar', methods=['GET'])
@login_required()
def menejerlar_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM menejerlar ORDER BY ism").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/menejerlar', methods=['POST'])
@login_required('admin')
def menejer_qosh():
    d = request.json or {}
    if not d.get('ism'):
        return jsonify({'error': 'Ism majburiy'}), 400
    conn = get_db()
    cur = conn.execute("INSERT INTO menejerlar (ism,telefon,izoh) VALUES (?,?,?)",
                       (d['ism'], d.get('telefon', ''), d.get('izoh', '')))
    conn.commit()
    mid = cur.lastrowid
    conn.close()
    audit(request.user['username'], 'qoshdi', 'menejer', mid, d['ism'])
    return jsonify({'status': 'ok', 'id': mid})


@app.route('/api/menejerlar/<int:mid>', methods=['PUT'])
@login_required('admin')
def menejer_yangilash(mid):
    d = request.json or {}
    conn = get_db()
    conn.execute("UPDATE menejerlar SET ism=?,telefon=?,izoh=? WHERE id=?",
                 (d['ism'], d.get('telefon', ''), d.get('izoh', ''), mid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'tahrirladi', 'menejer', mid, d.get('ism', ''))
    return jsonify({'status': 'ok'})


@app.route('/api/menejerlar/<int:mid>', methods=['DELETE'])
@login_required('admin')
def menejer_ochir(mid):
    conn = get_db()
    conn.execute("DELETE FROM menejerlar WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'menejer', mid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Operatsiyalar moduli
# ----------------------------------------------------------------------------
def hisobla(d, mahsulot):
    """Formulalar va statuslar bo'yicha qiymatlarni hisoblaydi."""
    otgr = int(d.get('otgr_kol', 0) or 0)
    vozvrat = int(d.get('vozvrat_kol', 0) or 0)
    prodaja = otgr - vozvrat                       # Продажа = Отгр - Возврат
    sebest = float(d.get('sebest', mahsulot['tannarx']) or 0)
    narx = float(d.get('sotuv_narx', mahsulot['sotuv_narx']) or 0)
    summa_prodaj = prodaja * narx                  # saleAmount = soldQuantity * salePrice
    cost_summa = prodaja * sebest                  # costAmount = soldQuantity * unitCost

    status = d.get('status', 'Отправлен')
    data_otgr = d.get('data_otgr', '')
    data_prodaj = d.get('data_prodaj', '')
    if status == 'Отправлен' and not data_otgr:
        data_otgr = today_str()                    # shipmentDate = currentDate
    if status in ('Продажа', 'Возврат') and not data_prodaj:
        data_prodaj = today_str()                  # saleDate = currentDate

    return {
        'otgr_kol': otgr, 'vozvrat_kol': vozvrat, 'prodaja': prodaja,
        'sebest': sebest, 'sotuv_narx': narx,
        'summa_prodaj': summa_prodaj, 'cost_summa': cost_summa,
        'status': status, 'data_otgr': data_otgr, 'data_prodaj': data_prodaj,
    }


def stock_delta(otgr, vozvrat):
    """newStock = currentStock - shippedQuantity + returnedQuantity"""
    return -otgr + vozvrat


def op_query(extra='', params=()):
    base = """SELECT o.*, m.nomi, m.artikul, m.kod, m.birlik, m.qoldiq AS ostatok,
                     k.nomi AS kontragent
              FROM operatsiyalar o
              LEFT JOIN mahsulotlar m ON o.mahsulot_id=m.id
              LEFT JOIN kontragentlar k ON o.kontragent_id=k.id """
    return base + extra, params


@app.route('/api/operatsiyalar', methods=['GET'])
@login_required()
def operatsiyalar_list():
    u = request.user
    conn = get_db()
    where, params = '', []
    if u['role'] != 'admin':
        where = "WHERE o.menejer=? "          # Menejer faqat o'z ma'lumotlarini ko'radi
        params.append(u['username'])
    sql, _ = op_query(where + "ORDER BY o.id DESC")
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route('/api/operatsiyalar', methods=['POST'])
@login_required()
def operatsiya_qosh():
    d = request.json or {}
    if not d.get('mahsulot_id'):
        return jsonify({'error': 'Mahsulot (artikul) tanlang'}), 400
    conn = get_db()
    m = conn.execute("SELECT * FROM mahsulotlar WHERE id=?", (d['mahsulot_id'],)).fetchone()
    if not m:
        conn.close()
        return jsonify({'error': 'Mahsulot topilmadi'}), 404

    v = hisobla(d, m)
    menejer = request.user['username'] if request.user['role'] != 'admin' \
        else d.get('menejer', request.user['username'])

    cur = conn.execute(
        """INSERT INTO operatsiyalar
           (sklad,mahsulot_id,otgr_kol,vozvrat_kol,prodaja,sebest,sotuv_narx,
            summa_prodaj,cost_summa,zakaz_nomer,status,dogovor,kontragent_id,
            data_otgr,data_prodaj,menejer,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.get('sklad', ''), d['mahsulot_id'], v['otgr_kol'], v['vozvrat_kol'], v['prodaja'],
         v['sebest'], v['sotuv_narx'], v['summa_prodaj'], v['cost_summa'],
         d.get('zakaz_nomer', ''), v['status'], d.get('dogovor', ''),
         d.get('kontragent_id'), v['data_otgr'], v['data_prodaj'], menejer, now_str()))
    oid = cur.lastrowid

    # Ombor qoldig'i va mahsulot statistikasi
    conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq+? WHERE id=?",
                 (stock_delta(v['otgr_kol'], v['vozvrat_kol']), d['mahsulot_id']))
    conn.execute("UPDATE mahsulotlar SET sotilgan=sotilgan+?, qaytarilgan=qaytarilgan+? WHERE id=?",
                 (max(v['prodaja'], 0), v['vozvrat_kol'], d['mahsulot_id']))
    conn.commit()
    conn.close()
    audit(menejer, 'qoshdi', 'operatsiya', oid, v['status'])
    return jsonify({'status': 'ok', 'id': oid})


@app.route('/api/operatsiyalar/<int:oid>', methods=['PUT'])
@login_required()
def operatsiya_yangilash(oid):
    d = request.json or {}
    conn = get_db()
    old = conn.execute("SELECT * FROM operatsiyalar WHERE id=?", (oid,)).fetchone()
    if not old:
        conn.close()
        return jsonify({'error': 'Topilmadi'}), 404
    if request.user['role'] != 'admin' and old['menejer'] != request.user['username']:
        conn.close()
        return jsonify({'error': 'Ruxsat yo\'q'}), 403

    mid = d.get('mahsulot_id', old['mahsulot_id'])
    m = conn.execute("SELECT * FROM mahsulotlar WHERE id=?", (mid,)).fetchone()
    v = hisobla(d, m)

    # Eski ta'sirni bekor qilamiz
    conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq-? WHERE id=?",
                 (stock_delta(old['otgr_kol'], old['vozvrat_kol']), old['mahsulot_id']))
    conn.execute("UPDATE mahsulotlar SET sotilgan=sotilgan-?, qaytarilgan=qaytarilgan-? WHERE id=?",
                 (max(old['prodaja'], 0), old['vozvrat_kol'], old['mahsulot_id']))

    conn.execute(
        """UPDATE operatsiyalar SET sklad=?,mahsulot_id=?,otgr_kol=?,vozvrat_kol=?,prodaja=?,
           sebest=?,sotuv_narx=?,summa_prodaj=?,cost_summa=?,zakaz_nomer=?,status=?,dogovor=?,
           kontragent_id=?,data_otgr=?,data_prodaj=? WHERE id=?""",
        (d.get('sklad', old['sklad']), mid, v['otgr_kol'], v['vozvrat_kol'], v['prodaja'],
         v['sebest'], v['sotuv_narx'], v['summa_prodaj'], v['cost_summa'],
         d.get('zakaz_nomer', old['zakaz_nomer']), v['status'],
         d.get('dogovor', old['dogovor']), d.get('kontragent_id', old['kontragent_id']),
         v['data_otgr'], v['data_prodaj'], oid))

    # Yangi ta'sir
    conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq+? WHERE id=?",
                 (stock_delta(v['otgr_kol'], v['vozvrat_kol']), mid))
    conn.execute("UPDATE mahsulotlar SET sotilgan=sotilgan+?, qaytarilgan=qaytarilgan+? WHERE id=?",
                 (max(v['prodaja'], 0), v['vozvrat_kol'], mid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'tahrirladi', 'operatsiya', oid, v['status'])
    return jsonify({'status': 'ok'})


@app.route('/api/operatsiyalar/<int:oid>', methods=['DELETE'])
@login_required()
def operatsiya_ochir(oid):
    conn = get_db()
    old = conn.execute("SELECT * FROM operatsiyalar WHERE id=?", (oid,)).fetchone()
    if not old:
        conn.close()
        return jsonify({'error': 'Topilmadi'}), 404
    if request.user['role'] != 'admin' and old['menejer'] != request.user['username']:
        conn.close()
        return jsonify({'error': 'Ruxsat yo\'q'}), 403
    # Ta'sirni bekor qilamiz
    conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq-? WHERE id=?",
                 (stock_delta(old['otgr_kol'], old['vozvrat_kol']), old['mahsulot_id']))
    conn.execute("UPDATE mahsulotlar SET sotilgan=sotilgan-?, qaytarilgan=qaytarilgan-? WHERE id=?",
                 (max(old['prodaja'], 0), old['vozvrat_kol'], old['mahsulot_id']))
    conn.execute("DELETE FROM operatsiyalar WHERE id=?", (oid,))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'ochirdi', 'operatsiya', oid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Dashboard
# ----------------------------------------------------------------------------
@app.route('/api/dashboard', methods=['GET'])
@login_required()
def dashboard():
    conn = get_db()
    u = request.user
    op_where, params = '', []
    if u['role'] != 'admin':
        op_where = "WHERE menejer=? "
        params.append(u['username'])

    jami_mahsulot = conn.execute("SELECT COUNT(*) n FROM mahsulotlar").fetchone()['n']
    jami_qoldiq = conn.execute("SELECT COALESCE(SUM(qoldiq),0) s FROM mahsulotlar").fetchone()['s']

    today = today_str()
    bugungi = conn.execute(
        f"SELECT COALESCE(SUM(summa_prodaj),0) s FROM operatsiyalar {op_where}"
        f"{'AND' if op_where else 'WHERE'} data_prodaj=?", params + [today]).fetchone()['s']

    oy = today[:7]
    oylik = conn.execute(
        f"SELECT COALESCE(SUM(summa_prodaj),0) s FROM operatsiyalar {op_where}"
        f"{'AND' if op_where else 'WHERE'} substr(data_prodaj,1,7)=?", params + [oy]).fetchone()['s']

    qaytarilgan = conn.execute(
        f"SELECT COALESCE(SUM(vozvrat_kol),0) s FROM operatsiyalar {op_where}",
        params).fetchone()['s']

    rr = conn.execute(
        f"SELECT COALESCE(SUM(summa_prodaj),0) sp, COALESCE(SUM(cost_summa),0) cs "
        f"FROM operatsiyalar {op_where}", params).fetchone()
    foyda = (rr['sp'] or 0) - (rr['cs'] or 0)

    past_qoldiq = conn.execute(
        "SELECT * FROM mahsulotlar WHERE qoldiq<=5 ORDER BY qoldiq LIMIT 20").fetchall()
    conn.close()
    return jsonify({
        'jami_mahsulot': jami_mahsulot,
        'jami_qoldiq': jami_qoldiq,
        'bugungi_sotuv': bugungi,
        'oylik_sotuv': oylik,
        'qaytarilgan': qaytarilgan,
        'foyda': foyda,
        'past_qoldiq': [mahsulot_dict(r) for r in past_qoldiq],
    })


# ----------------------------------------------------------------------------
# Menejer KPI + TOP 10
# ----------------------------------------------------------------------------
@app.route('/api/kpi', methods=['GET'])
@login_required()
def kpi():
    conn = get_db()
    rows = conn.execute("""
        SELECT menejer,
               COALESCE(SUM(prodaja),0) sotilgan_son,
               COALESCE(SUM(summa_prodaj),0) sotuv_summa,
               COALESCE(SUM(vozvrat_kol),0) qaytarilgan,
               COALESCE(SUM(summa_prodaj - cost_summa),0) foyda
        FROM operatsiyalar
        WHERE menejer != ''
        GROUP BY menejer
        ORDER BY foyda DESC
    """).fetchall()
    conn.close()
    data = [dict(r) for r in rows]
    return jsonify({'menejerlar': data, 'top10': data[:10]})


# ----------------------------------------------------------------------------
# Hisobotlar
# ----------------------------------------------------------------------------
@app.route('/api/hisobot/<turi>', methods=['GET'])
@login_required()
def hisobot(turi):
    conn = get_db()
    u = request.user
    where, params = '', []
    if u['role'] != 'admin':
        where = "WHERE o.menejer=? "
        params.append(u['username'])

    if turi == 'sotuv':
        sql, _ = op_query(where + (
            "AND" if where else "WHERE") + " o.status='Продажа' ORDER BY o.data_prodaj DESC")
        rows = conn.execute(sql, params).fetchall()
    elif turi == 'qaytarish':
        sql, _ = op_query(where + (
            "AND" if where else "WHERE") + " o.vozvrat_kol>0 ORDER BY o.id DESC")
        rows = conn.execute(sql, params).fetchall()
    elif turi == 'ombor':
        rows = conn.execute("SELECT * FROM mahsulotlar ORDER BY nomi").fetchall()
        conn.close()
        return jsonify([mahsulot_dict(r) for r in rows])
    else:
        conn.close()
        return jsonify({'error': 'Noma\'lum hisobot'}), 400
    conn.close()
    return jsonify([dict(r) for r in rows])


# ----------------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------------
@app.route('/api/audit', methods=['GET'])
@login_required('admin')
def audit_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 500").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ----------------------------------------------------------------------------
# Excel (CSV) export / import
# ----------------------------------------------------------------------------
@app.route('/api/export/mahsulotlar', methods=['GET'])
@login_required()
def export_mahsulotlar():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mahsulotlar ORDER BY nomi").fetchall()
    conn.close()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['kod', 'artikul', 'nomi', 'birlik', 'qoldiq', 'tannarx',
                'sotuv_narx', 'sotilgan', 'qaytarilgan'])
    for r in rows:
        w.writerow([r['kod'], r['artikul'], r['nomi'], r['birlik'], r['qoldiq'],
                    r['tannarx'], r['sotuv_narx'], r['sotilgan'], r['qaytarilgan']])
    return Response('﻿' + out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=mahsulotlar.csv'})


@app.route('/api/export/operatsiyalar', methods=['GET'])
@login_required()
def export_operatsiyalar():
    u = request.user
    conn = get_db()
    where, params = '', []
    if u['role'] != 'admin':
        where = "WHERE o.menejer=? "
        params.append(u['username'])
    sql, _ = op_query(where + "ORDER BY o.id DESC")
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    out = io.StringIO()
    w = csv.writer(out)
    cols = ['sklad', 'artikul', 'nomi', 'ostatok', 'otgr_kol', 'vozvrat_kol', 'prodaja',
            'sebest', 'summa_prodaj', 'zakaz_nomer', 'status', 'dogovor', 'kontragent',
            'data_otgr', 'data_prodaj', 'menejer']
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] if c in r.keys() else '' for c in cols])
    return Response('﻿' + out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=operatsiyalar.csv'})


@app.route('/api/import/mahsulotlar', methods=['POST'])
@login_required('admin')
def import_mahsulotlar():
    """CSV matni qabul qiladi: {csv: '...'}"""
    d = request.json or {}
    text = d.get('csv', '')
    if not text:
        return jsonify({'error': 'CSV matni bo\'sh'}), 400
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    conn = get_db()
    n = 0
    for row in reader:
        nomi = (row.get('nomi') or '').strip()
        if not nomi:
            continue
        conn.execute(
            """INSERT INTO mahsulotlar (kod,artikul,nomi,birlik,qoldiq,tannarx,sotuv_narx,created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (row.get('kod', ''), row.get('artikul', ''), nomi, row.get('birlik', 'dona') or 'dona',
             int(float(row.get('qoldiq', 0) or 0)), float(row.get('tannarx', 0) or 0),
             float(row.get('sotuv_narx', 0) or 0), now_str()))
        n += 1
    conn.commit()
    conn.close()
    audit(request.user['username'], 'import', 'mahsulot', None, f'{n} ta')
    return jsonify({'status': 'ok', 'qoshildi': n})


# ----------------------------------------------------------------------------
# Haqiqiy Excel (.xlsx) export
# ----------------------------------------------------------------------------
def xlsx_response(sheet_name, headers, rows, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(headers)
    for r in rows:
        ws.append(r)
    # ustun kengligi
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[chr(64 + i) if i <= 26 else 'A'].width = max(12, len(str(h)) + 2)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        buf.read(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'})


@app.route('/api/xlsx/mahsulotlar', methods=['GET'])
@login_required()
def xlsx_mahsulotlar():
    if not HAS_XLSX:
        return jsonify({'error': 'openpyxl o\'rnatilmagan'}), 501
    conn = get_db()
    rows = conn.execute("SELECT * FROM mahsulotlar ORDER BY nomi").fetchall()
    conn.close()
    headers = ['Kod', 'Artikul', 'Nomi', 'Birlik', 'Qoldiq', 'Tannarx',
               'Sotuv narx', 'Sotilgan', 'Qaytarilgan']
    data = [[r['kod'], r['artikul'], r['nomi'], r['birlik'], r['qoldiq'],
             r['tannarx'], r['sotuv_narx'], r['sotilgan'], r['qaytarilgan']] for r in rows]
    return xlsx_response('Mahsulotlar', headers, data, 'mahsulotlar.xlsx')


@app.route('/api/xlsx/operatsiyalar', methods=['GET'])
@login_required()
def xlsx_operatsiyalar():
    if not HAS_XLSX:
        return jsonify({'error': 'openpyxl o\'rnatilmagan'}), 501
    u = request.user
    conn = get_db()
    where, params = '', []
    if u['role'] != 'admin':
        where = "WHERE o.menejer=? "
        params.append(u['username'])
    sql, _ = op_query(where + "ORDER BY o.id DESC")
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    headers = ['Sklad', 'Artikul', 'Nomi', 'Ostatok', 'Otgr', 'Vozvrat', 'Prodaja',
               'Sebest', 'Summa prodaj', 'Zakaz №', 'Status', 'Dogovor', 'Kontragent',
               'Data otgr', 'Data prodaj', 'Menejer']
    keys = ['sklad', 'artikul', 'nomi', 'ostatok', 'otgr_kol', 'vozvrat_kol', 'prodaja',
            'sebest', 'summa_prodaj', 'zakaz_nomer', 'status', 'dogovor', 'kontragent',
            'data_otgr', 'data_prodaj', 'menejer']
    data = [[r[k] if k in r.keys() else '' for k in keys] for r in rows]
    return xlsx_response('Operatsiyalar', headers, data, 'operatsiyalar.xlsx')


# ----------------------------------------------------------------------------
# Parol o'zgartirish
# ----------------------------------------------------------------------------
@app.route('/api/change-password', methods=['POST'])
@login_required()
def change_password():
    d = request.json or {}
    if len(d.get('new', '')) < 4:
        return jsonify({'error': 'Yangi parol kamida 4 belgidan iborat bo\'lsin'}), 400
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (request.user['id'],)).fetchone()
    if not verify_password(d.get('old', ''), u['password_hash']):
        conn.close()
        return jsonify({'error': 'Joriy parol noto\'g\'ri'}), 400
    conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                 (hash_password(d['new']), request.user['id']))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'parol_ozgartirdi', 'foydalanuvchi', request.user['id'])
    return jsonify({'status': 'ok'})


@app.route('/api/users/<int:uid>/password', methods=['PUT'])
@login_required('admin')
def admin_reset_password(uid):
    d = request.json or {}
    if len(d.get('new', '')) < 4:
        return jsonify({'error': 'Parol kamida 4 belgidan iborat bo\'lsin'}), 400
    conn = get_db()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(d['new']), uid))
    conn.commit()
    conn.close()
    audit(request.user['username'], 'parol_tikladi', 'foydalanuvchi', uid)
    return jsonify({'status': 'ok'})


# ----------------------------------------------------------------------------
# Grafiklar uchun ma'lumot (oxirgi 6 oy sotuvi + menejerlar)
# ----------------------------------------------------------------------------
@app.route('/api/charts', methods=['GET'])
@login_required()
def charts():
    conn = get_db()
    u = request.user
    where, params = '', []
    if u['role'] != 'admin':
        where = "AND menejer=? "
        params.append(u['username'])

    # oxirgi 6 oy
    months = []
    y, m = date.today().year, date.today().month
    for _ in range(6):
        months.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()

    seriya = []
    for mo in months:
        r = conn.execute(
            f"SELECT COALESCE(SUM(summa_prodaj),0) s FROM operatsiyalar "
            f"WHERE substr(data_prodaj,1,7)=? {where}", [mo] + params).fetchone()
        seriya.append({'oy': mo, 'summa': r['s'] or 0})

    # status taqsimoti
    statlar = conn.execute(
        f"SELECT status, COUNT(*) n FROM operatsiyalar WHERE 1=1 {where} GROUP BY status",
        params).fetchall()
    conn.close()
    return jsonify({
        'oylik': seriya,
        'statuslar': [dict(s) for s in statlar],
    })


# ----------------------------------------------------------------------------
# Frontend
# ----------------------------------------------------------------------------
@app.route('/')
def index():
    return open('index.html', encoding='utf-8').read()


init_db()

if __name__ == '__main__':
    print("=" * 50)
    print("  MedStock ERP ishga tushdi!")
    print("  Brauzerda oching: http://localhost:5000")
    print("  Login:  admin   Parol:  admin123")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
