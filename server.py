from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from datetime import datetime

app = Flask(__name__)
CORS(app)
DB = 'ombor.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS mahsulotlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        razmeri TEXT NOT NULL,
        lot_raqami TEXT DEFAULT '',
        tannarx REAL DEFAULT 0,
        sotuv_narx REAL DEFAULT 0,
        qoldiq INTEGER DEFAULT 0,
        izoh TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS kontragentlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ismi TEXT NOT NULL,
        telefon TEXT DEFAULT '',
        manzil TEXT DEFAULT '',
        izoh TEXT DEFAULT ''
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS kirimlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mahsulot_id INTEGER,
        miqdor INTEGER,
        tannarx REAL DEFAULT 0,
        sana TEXT,
        izoh TEXT DEFAULT '',
        FOREIGN KEY (mahsulot_id) REFERENCES mahsulotlar(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS zakazlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kontragent_id INTEGER,
        sana TEXT,
        holat TEXT DEFAULT 'Jarayonda',
        tolov REAL DEFAULT 0,
        med_nalog REAL DEFAULT 0,
        izoh TEXT DEFAULT '',
        FOREIGN KEY (kontragent_id) REFERENCES kontragentlar(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS zakaz_tovarlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        zakaz_id INTEGER,
        mahsulot_id INTEGER,
        miqdor INTEGER DEFAULT 1,
        sotuv_narx REAL DEFAULT 0,
        holat TEXT DEFAULT 'Chiqarilgan',
        FOREIGN KEY (zakaz_id) REFERENCES zakazlar(id),
        FOREIGN KEY (mahsulot_id) REFERENCES mahsulotlar(id)
    )''')
    conn.commit()
    conn.close()

init_db()

@app.route('/api/mahsulotlar', methods=['GET'])
def mahsulotlar_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM mahsulotlar ORDER BY nomi").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/mahsulotlar', methods=['POST'])
def mahsulot_qosh():
    d = request.json
    conn = get_db()
    conn.execute("INSERT INTO mahsulotlar (nomi,razmeri,lot_raqami,tannarx,sotuv_narx,qoldiq,izoh) VALUES (?,?,?,?,?,?,?)",
        (d['nomi'],d['razmeri'],d.get('lot_raqami',''),d.get('tannarx',0),d.get('sotuv_narx',0),d.get('qoldiq',0),d.get('izoh','')))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/mahsulotlar/<int:mid>', methods=['PUT'])
def mahsulot_yangilash(mid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE mahsulotlar SET nomi=?,razmeri=?,lot_raqami=?,tannarx=?,sotuv_narx=?,qoldiq=?,izoh=? WHERE id=?",
        (d['nomi'],d['razmeri'],d.get('lot_raqami',''),d.get('tannarx',0),d.get('sotuv_narx',0),d.get('qoldiq',0),d.get('izoh',''),mid))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/mahsulotlar/<int:mid>', methods=['DELETE'])
def mahsulot_ochir(mid):
    conn = get_db()
    conn.execute("DELETE FROM mahsulotlar WHERE id=?", (mid,))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/kontragentlar', methods=['GET'])
def kontragentlar_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM kontragentlar ORDER BY ismi").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/kontragentlar', methods=['POST'])
def kontragent_qosh():
    d = request.json
    conn = get_db()
    conn.execute("INSERT INTO kontragentlar (ismi,telefon,manzil,izoh) VALUES (?,?,?,?)",
        (d['ismi'],d.get('telefon',''),d.get('manzil',''),d.get('izoh','')))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/kontragentlar/<int:kid>', methods=['PUT'])
def kontragent_yangilash(kid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE kontragentlar SET ismi=?,telefon=?,manzil=?,izoh=? WHERE id=?",
        (d['ismi'],d.get('telefon',''),d.get('manzil',''),d.get('izoh',''),kid))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/kontragentlar/<int:kid>', methods=['DELETE'])
def kontragent_ochir(kid):
    conn = get_db()
    conn.execute("DELETE FROM kontragentlar WHERE id=?", (kid,))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/kirim', methods=['POST'])
def kirim_qosh():
    d = request.json
    conn = get_db()
    sana = datetime.now().strftime("%Y-%m-%d %H:%M")
    conn.execute("INSERT INTO kirimlar (mahsulot_id,miqdor,tannarx,sana,izoh) VALUES (?,?,?,?,?)",
        (d['mahsulot_id'],d['miqdor'],d.get('tannarx',0),sana,d.get('izoh','')))
    conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq+? WHERE id=?", (d['miqdor'],d['mahsulot_id']))
    if d.get('tannarx',0)>0:
        conn.execute("UPDATE mahsulotlar SET tannarx=? WHERE id=?", (d['tannarx'],d['mahsulot_id']))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/kirimlar', methods=['GET'])
def kirimlar_list():
    conn = get_db()
    rows = conn.execute("SELECT k.id,m.nomi,m.razmeri,k.miqdor,k.tannarx,k.sana,k.izoh FROM kirimlar k JOIN mahsulotlar m ON k.mahsulot_id=m.id ORDER BY k.id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/zakazlar', methods=['GET'])
def zakazlar_list():
    holat = request.args.get('holat','')
    conn = get_db()
    q = "SELECT z.id,k.ismi,k.telefon,z.sana,z.holat,z.tolov,z.med_nalog,z.izoh FROM zakazlar z JOIN kontragentlar k ON z.kontragent_id=k.id"
    if holat:
        rows = conn.execute(q+" WHERE z.holat=? ORDER BY z.id DESC",(holat,)).fetchall()
    else:
        rows = conn.execute(q+" ORDER BY z.id DESC").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/zakazlar', methods=['POST'])
def zakaz_qosh():
    d = request.json
    conn = get_db()
    sana = datetime.now().strftime("%Y-%m-%d %H:%M")
    cur = conn.execute("INSERT INTO zakazlar (kontragent_id,sana,tolov,med_nalog,izoh) VALUES (?,?,?,?,?)",
        (d['kontragent_id'],sana,d.get('tolov',0),d.get('med_nalog',0),d.get('izoh','')))
    zid = cur.lastrowid
    for t in d.get('tovarlar',[]):
        conn.execute("INSERT INTO zakaz_tovarlar (zakaz_id,mahsulot_id,miqdor,sotuv_narx) VALUES (?,?,?,?)",
            (zid,t['mahsulot_id'],t['miqdor'],t.get('sotuv_narx',0)))
        conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq-? WHERE id=?", (t['miqdor'],t['mahsulot_id']))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok','zakaz_id':zid})

@app.route('/api/zakazlar/<int:zid>', methods=['GET'])
def zakaz_detail(zid):
    conn = get_db()
    z = conn.execute("SELECT z.*,k.ismi,k.telefon FROM zakazlar z JOIN kontragentlar k ON z.kontragent_id=k.id WHERE z.id=?",(zid,)).fetchone()
    t = conn.execute("SELECT zt.id,m.nomi,m.razmeri,m.lot_raqami,zt.miqdor,zt.sotuv_narx,zt.holat FROM zakaz_tovarlar zt JOIN mahsulotlar m ON zt.mahsulot_id=m.id WHERE zt.zakaz_id=?",(zid,)).fetchall()
    conn.close()
    return jsonify({'zakaz':dict(z),'tovarlar':[dict(x) for x in t]})

@app.route('/api/zakazlar/<int:zid>/tolov', methods=['PUT'])
def tolov_yangilash(zid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE zakazlar SET tolov=?,med_nalog=? WHERE id=?",(d['tolov'],d['med_nalog'],zid))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/zakaz_tovar/<int:tid>/vozvrat', methods=['PUT'])
def vozvrat(tid):
    conn = get_db()
    row = conn.execute("SELECT mahsulot_id,miqdor,holat FROM zakaz_tovarlar WHERE id=?",(tid,)).fetchone()
    if row and row['holat']=='Chiqarilgan':
        conn.execute("UPDATE zakaz_tovarlar SET holat='Qaytarildi' WHERE id=?",(tid,))
        conn.execute("UPDATE mahsulotlar SET qoldiq=qoldiq+? WHERE id=?",(row['miqdor'],row['mahsulot_id']))
        conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/zakaz_tovar/<int:tid>/sotildi', methods=['PUT'])
def tovar_sotildi(tid):
    d = request.json
    conn = get_db()
    conn.execute("UPDATE zakaz_tovarlar SET holat='Sotildi',sotuv_narx=? WHERE id=?",(d.get('sotuv_narx',0),tid))
    zid = conn.execute("SELECT zakaz_id FROM zakaz_tovarlar WHERE id=?",(tid,)).fetchone()['zakaz_id']
    holatlar = conn.execute("SELECT holat FROM zakaz_tovarlar WHERE zakaz_id=?",(zid,)).fetchall()
    if all(h['holat'] in ['Sotildi','Qaytarildi'] for h in holatlar):
        conn.execute("UPDATE zakazlar SET holat='Sotildi' WHERE id=?",(zid,))
    conn.commit()
    conn.close()
    return jsonify({'status':'ok'})

@app.route('/api/hisobot', methods=['GET'])
def hisobot():
    conn = get_db()
    jami_zakaz = conn.execute("SELECT COUNT(*) as n FROM zakazlar").fetchone()['n']
    jarayonda = conn.execute("SELECT COUNT(*) as n FROM zakazlar WHERE holat='Jarayonda'").fetchone()['n']
    sotildi = conn.execute("SELECT COUNT(*) as n FROM zakazlar WHERE holat='Sotildi'").fetchone()['n']
    r = conn.execute("SELECT SUM(tolov) as t,SUM(med_nalog) as m FROM zakazlar WHERE holat='Sotildi'").fetchone()
    jami_tolov = r['t'] or 0
    jami_nalog = r['m'] or 0
    vozvrat_son = conn.execute("SELECT COUNT(*) as n FROM zakaz_tovarlar WHERE holat='Qaytarildi'").fetchone()['n']
    past_qoldiq = conn.execute("SELECT * FROM mahsulotlar WHERE qoldiq<=5 ORDER BY qoldiq").fetchall()
    conn.close()
    return jsonify({'jami_zakaz':jami_zakaz,'jarayonda':jarayonda,'sotildi':sotildi,
        'jami_tolov':jami_tolov,'jami_nalog':jami_nalog,'sof_daromad':jami_tolov-jami_nalog,
        'vozvrat_son':vozvrat_son,'past_qoldiq':[dict(r) for r in past_qoldiq]})

@app.route('/')
def index():
    return open('index.html',encoding='utf-8').read()

if __name__ == '__main__':
    print("="*50)
    print("Server ishga tushdi!")
    print("Brauzerda oching: http://localhost:5000")
    print("Boshqa kompyuterdan: http://YOUR_IP:5000")
    print("="*50)
    app.run(host='0.0.0.0',port=5000,debug=False)
