"""Code Nova educational clinical management demo. Synthetic data only."""
import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE = Path(__file__).resolve().parent
app = Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY', 'development-only-change-me'), DATABASE=os.environ.get('DATABASE', str(BASE / 'code_nova.db')), SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax')

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','physician','staff','patient')), name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS patients (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id), name TEXT NOT NULL, dob TEXT NOT NULL, phone TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id), physician_id INTEGER NOT NULL REFERENCES users(id), start_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled' CHECK(status IN ('scheduled','confirmed','checked_in','completed','cancelled')), created_by INTEGER NOT NULL REFERENCES users(id));
CREATE TABLE IF NOT EXISTS encounters (id INTEGER PRIMARY KEY, appointment_id INTEGER UNIQUE NOT NULL REFERENCES appointments(id), physician_id INTEGER NOT NULL REFERENCES users(id), subjective TEXT NOT NULL DEFAULT '', objective TEXT NOT NULL DEFAULT '', assessment TEXT NOT NULL DEFAULT '', plan TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','finalized')), updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS invoices (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id), description TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('draft','open','paid_simulated','overdue')));
CREATE INDEX IF NOT EXISTS idx_appointments_physician_time ON appointments(physician_id,start_at);
'''


def db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


@app.teardown_appcontext
def close_db(exc):
    conn = g.pop('db', None)
    if conn is not None:
        conn.close()


def seed():
    conn = db()
    conn.executescript(SCHEMA)
    fixtures = [
        ('admin.demo@example.test', 'Admin Demo', 'admin'),
        ('doctor.demo@example.test', 'Dr. Morgan', 'physician'),
        ('staff.demo@example.test', 'Clinic Staff', 'staff'),
        ('patient.demo@example.test', 'Test Patient Alpha', 'patient'),
    ]
    for email, name, role in fixtures:
        conn.execute('INSERT OR IGNORE INTO users(email,password_hash,role,name) VALUES(?,?,?,?)',
                     (email, generate_password_hash('DemoPass123!'), role, name))
    patient_user = conn.execute("SELECT id FROM users WHERE email='patient.demo@example.test'").fetchone()['id']
    conn.execute('INSERT OR IGNORE INTO patients(id,user_id,name,dob,phone) VALUES(1,?,?,?,?)',
                 (patient_user, 'Test Patient Alpha', '2000-01-01', '555-0100'))
    conn.execute('INSERT OR IGNORE INTO patients(id,user_id,name,dob,phone) VALUES(2,NULL,?,?,?)',
                 ('Test Patient Beta','1998-02-02','555-0101'))
    conn.commit()


@app.before_request
def load_user_and_csrf():
    if 'csrf' not in session:
        session['csrf'] = secrets.token_hex(24)
    g.user = db().execute('SELECT id,email,name,role FROM users WHERE id=?',(session.get('uid',-1),)).fetchone()
    if request.method == 'POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf', '')):
        abort(400, 'Invalid form token; reload the page and try again.')


@app.context_processor
def globals_for_templates():
    return {'csrf': session.get('csrf',''), 'me': g.get('user')}


def require(*roles):
    def decorator(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if not g.user:
                return redirect(url_for('login'))
            if roles and g.user['role'] not in roles:
                abort(403)
            return func(*args, **kwargs)
        return wrapped
    return decorator


@app.route('/')
def index():
    return redirect(url_for('dashboard') if g.user else url_for('login'))


@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        u = db().execute('SELECT * FROM users WHERE email=?',(email,)).fetchone()
        if u and check_password_hash(u['password_hash'],request.form.get('password','')):
            session.clear()
            session['uid'] = u['id']
            session['csrf'] = secrets.token_hex(24)
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.post('/logout')
@require()
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@require()
def dashboard():
    role = g.user['role']
    if role == 'patient':
        appointments = db().execute('''SELECT a.*,u.name AS doctor FROM appointments a JOIN users u ON u.id=a.physician_id JOIN patients p ON p.id=a.patient_id WHERE p.user_id=? ORDER BY start_at''',(g.user['id'],)).fetchall()
        return render_template('dashboard.html', appointments=appointments, count=len(appointments), patients_count=None, portal=True)
    appointments = db().execute('''SELECT a.*,p.name AS patient,u.name AS doctor FROM appointments a JOIN patients p ON p.id=a.patient_id JOIN users u ON u.id=a.physician_id WHERE (? != 'physician' OR a.physician_id=?) ORDER BY start_at''',(role,g.user['id'])).fetchall()
    patient_count = db().execute('SELECT COUNT(*) AS n FROM patients').fetchone()['n'] if role in ('admin','staff') else None
    return render_template('dashboard.html',appointments=appointments,count=len(appointments),patients_count=patient_count,portal=False)


@app.route('/patients',methods=['GET','POST'])
@require('staff','admin','physician')
def patients():
    if request.method == 'POST':
        if g.user['role'] not in ('staff','admin'): abort(403)
        name=request.form.get('name','').strip()
        dob=request.form.get('dob','')
        phone=request.form.get('phone','').strip()
        try:
            datetime.strptime(dob,'%Y-%m-%d')
        except ValueError:
            flash('Enter a valid date of birth.', 'error')
        else:
            if name and phone and len(name)<=120 and len(phone)<=40:
                db().execute('INSERT INTO patients(name,dob,phone) VALUES(?,?,?)',(name,dob,phone))
                db().commit()
                flash('Synthetic patient added.', 'success')
                return redirect(url_for('patients'))
            flash('Name and phone are required.', 'error')
    term=request.args.get('q','').strip()
    records=db().execute('SELECT * FROM patients WHERE name LIKE ? OR CAST(id AS TEXT)=? ORDER BY id',(f'%{term}%',term)).fetchall() if term else db().execute('SELECT * FROM patients ORDER BY id').fetchall()
    return render_template('patients.html',patients=records,term=term)


def permitted_patient(patient_id):
    if g.user['role']=='patient':
        return db().execute('SELECT 1 FROM patients WHERE id=? AND user_id=?',(patient_id,g.user['id'])).fetchone() is not None
    return g.user['role'] in ('staff','admin')


def valid_start(value):
    try:
        d=datetime.strptime(value,'%Y-%m-%dT%H:%M')
        if d < datetime.now(): return None
        return d
    except ValueError:
        return None


@app.route('/appointments',methods=['GET','POST'])
@require()
def appointments():
    if request.method=='POST':
        if g.user['role']=='physician': abort(403)
        try: patient_id=int(request.form.get('patient_id',''))
        except ValueError: abort(400)
        if not permitted_patient(patient_id): abort(403)
        doctor_id=request.form.get('physician_id','')
        doc=db().execute("SELECT id FROM users WHERE id=? AND role='physician'",(doctor_id,)).fetchone()
        start=valid_start(request.form.get('start_at',''))
        if not doc or not start:
            flash('Choose a physician and future appointment time.', 'error')
        else:
            stamp=start.strftime('%Y-%m-%dT%H:%M')
            existing=db().execute("SELECT start_at FROM appointments WHERE physician_id=? AND status!='cancelled'",(doctor_id,)).fetchall()
            if any(abs((datetime.strptime(r['start_at'],'%Y-%m-%dT%H:%M')-start).total_seconds())<1800 for r in existing):
                flash('Appointment conflicts with an existing 30-minute slot.', 'error')
            else:
                db().execute('INSERT INTO appointments(patient_id,physician_id,start_at,created_by) VALUES(?,?,?,?)',(patient_id,doctor_id,stamp,g.user['id']))
                db().commit()
                flash('Appointment scheduled.', 'success')
                return redirect(url_for('appointments'))
    if g.user['role']=='patient':
        patient_list=db().execute('SELECT id,name FROM patients WHERE user_id=?',(g.user['id'],)).fetchall()
        rows=db().execute('''SELECT a.*,p.name AS patient,u.name AS doctor FROM appointments a JOIN patients p ON a.patient_id=p.id JOIN users u ON a.physician_id=u.id WHERE p.user_id=? ORDER BY start_at''',(g.user['id'],)).fetchall()
    elif g.user['role']=='physician':
        patient_list=[]
        rows=db().execute('''SELECT a.*,p.name AS patient,u.name AS doctor FROM appointments a JOIN patients p ON a.patient_id=p.id JOIN users u ON a.physician_id=u.id WHERE a.physician_id=? ORDER BY start_at''',(g.user['id'],)).fetchall()
    else:
        patient_list=db().execute('SELECT id,name FROM patients ORDER BY name').fetchall()
        rows=db().execute('''SELECT a.*,p.name AS patient,u.name AS doctor FROM appointments a JOIN patients p ON a.patient_id=p.id JOIN users u ON a.physician_id=u.id ORDER BY start_at''').fetchall()
    doctors=db().execute("SELECT id,name FROM users WHERE role='physician' ORDER BY name").fetchall()
    return render_template('appointments.html',records=rows,patients=patient_list,doctors=doctors)


@app.post('/appointments/<int:appointment_id>/cancel')
@require()
def cancel_appointment(appointment_id):
    row=db().execute('''SELECT a.*,p.user_id FROM appointments a JOIN patients p ON p.id=a.patient_id WHERE a.id=?''',(appointment_id,)).fetchone()
    if not row: abort(404)
    if g.user['role']=='patient' and row['user_id']!=g.user['id']: abort(403)
    if g.user['role']=='physician' and row['physician_id']!=g.user['id']: abort(403)
    if request.form.get('confirm')!='yes': abort(400)
    if row['status']!='completed':
        db().execute("UPDATE appointments SET status='cancelled' WHERE id=?",(appointment_id,))
        db().commit()
    return redirect(url_for('appointments'))


@app.post('/appointments/<int:appointment_id>/status')
@require('admin','staff','physician')
def appointment_status(appointment_id):
    row=db().execute('SELECT * FROM appointments WHERE id=?',(appointment_id,)).fetchone()
    if not row: abort(404)
    if g.user['role']=='physician' and row['physician_id']!=g.user['id']: abort(403)
    new=request.form.get('status','')
    allowed={'scheduled':('confirmed','cancelled'),'confirmed':('checked_in','cancelled'),'checked_in':('completed',),'completed':(),'cancelled':()}
    if new not in allowed[row['status']]: abort(400)
    db().execute('UPDATE appointments SET status=? WHERE id=?',(new,appointment_id))
    db().commit()
    return redirect(url_for('appointments'))


@app.route('/appointments/<int:appointment_id>/reschedule',methods=['POST'])
@require('admin','staff','patient')
def reschedule_appointment(appointment_id):
    row=db().execute('SELECT a.*,p.user_id FROM appointments a JOIN patients p ON p.id=a.patient_id WHERE a.id=?',(appointment_id,)).fetchone()
    if not row: abort(404)
    if g.user['role']=='patient' and row['user_id']!=g.user['id']: abort(403)
    if row['status'] in ('completed','cancelled'): abort(400)
    start=valid_start(request.form.get('start_at',''))
    if not start: abort(400)
    other=db().execute("SELECT start_at FROM appointments WHERE physician_id=? AND id!=? AND status!='cancelled'",(row['physician_id'],appointment_id)).fetchall()
    if any(abs((datetime.strptime(r['start_at'],'%Y-%m-%dT%H:%M')-start).total_seconds())<1800 for r in other):
        flash('That rescheduled slot conflicts with another appointment.','error')
        return redirect(url_for('appointments'))
    db().execute("UPDATE appointments SET start_at=?,status='scheduled' WHERE id=?",(start.strftime('%Y-%m-%dT%H:%M'),appointment_id))
    db().commit()
    flash('Appointment rescheduled.','success')
    return redirect(url_for('appointments'))


@app.route('/encounters',methods=['GET','POST'])
@require('physician')
def encounters():
    if request.method=='POST':
        try: appointment_id=int(request.form.get('appointment_id',''))
        except ValueError: abort(400)
        ap=db().execute("SELECT id,physician_id,status FROM appointments WHERE id=?",(appointment_id,)).fetchone()
        if not ap or ap['physician_id']!=g.user['id']: abort(403)
        if ap['status']=='cancelled': abort(400)
        db().execute('INSERT OR IGNORE INTO encounters(appointment_id,physician_id) VALUES(?,?)',(appointment_id,g.user['id']))
        db().commit()
        return redirect(url_for('encounter_detail',appointment_id=appointment_id))
    records=db().execute('''SELECT a.id,a.start_at,a.status,p.name AS patient,e.status AS note_status
        FROM appointments a JOIN patients p ON p.id=a.patient_id LEFT JOIN encounters e ON e.appointment_id=a.id
        WHERE a.physician_id=? ORDER BY a.start_at''',(g.user['id'],)).fetchall()
    return render_template('encounters.html',records=records)


@app.route('/encounters/<int:appointment_id>',methods=['GET','POST'])
@require('physician')
def encounter_detail(appointment_id):
    row=db().execute('''SELECT e.*,a.start_at,p.name AS patient FROM encounters e
      JOIN appointments a ON a.id=e.appointment_id JOIN patients p ON p.id=a.patient_id
      WHERE e.appointment_id=? AND e.physician_id=?''',(appointment_id,g.user['id'])).fetchone()
    if not row: abort(404)
    if request.method=='POST':
        if row['status']=='finalized': abort(400)
        notes=[request.form.get(k,'').strip() for k in ('subjective','objective','assessment','plan')]
        if any(len(n)>4000 for n in notes): abort(400)
        status='finalized' if request.form.get('action')=='finalize' else 'draft'
        if status=='finalized' and not all(notes):
            flash('Complete all four note fields before finalizing.','error')
        else:
            db().execute('''UPDATE encounters SET subjective=?,objective=?,assessment=?,plan=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',(*notes,status,row['id']))
            db().commit()
            flash('Encounter note saved.','success')
            return redirect(url_for('encounter_detail',appointment_id=appointment_id))
    return render_template('encounter_detail.html',encounter=row)


@app.route('/billing',methods=['GET','POST'])
@require('admin')
def billing():
    if request.method=='POST':
        try:
            pid=int(request.form.get('patient_id',''))
            amount=int(round(float(request.form.get('amount',''))*100))
        except (ValueError,OverflowError): abort(400)
        description=request.form.get('description','').strip()
        if not description or len(description)>200 or not 0<=amount<=100000000: abort(400)
        if not db().execute('SELECT 1 FROM patients WHERE id=?',(pid,)).fetchone(): abort(400)
        db().execute('INSERT INTO invoices(patient_id,description,amount_cents) VALUES(?,?,?)',(pid,description,amount))
        db().commit()
        flash('Synthetic invoice created. No payment was processed.','success')
        return redirect(url_for('billing'))
    invoices=db().execute('''SELECT i.*,p.name AS patient FROM invoices i JOIN patients p ON i.patient_id=p.id ORDER BY i.id DESC''').fetchall()
    patients=db().execute('SELECT id,name FROM patients ORDER BY name').fetchall()
    total=sum(i['amount_cents'] for i in invoices)
    return render_template('billing.html',invoices=invoices,patients=patients,total=total)


@app.route('/modules/<module>')
@require()
def module(module):
    details={
        'encounters': ('Encounter Workspace',('physician',)),
        'prescriptions': ('Prescriptions & Medication Review',('physician',)),
        'billing': ('Billing Overview',('admin',)),
    }
    if module not in details: abort(404)
    title,roles=details[module]
    if g.user['role'] not in roles: abort(403)
    if module=='encounters': return redirect(url_for('encounters'))
    if module=='billing': return redirect(url_for('billing'))
    return render_template('planned.html',title=title)


@app.cli.command('init-db')
def init_command():
    seed()
    print('Initialized synthetic demo database.')


if __name__=='__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG')=='1')
