import pytest
from app import app, seed, db

@pytest.fixture()
def client(tmp_path):
    app.config.update(TESTING=True, DATABASE=str(tmp_path/'test.db'), SECRET_KEY='tests-only')
    with app.app_context(): seed()
    with app.test_client() as c: yield c


def token(c):
    with c.session_transaction() as s:
        return s.get('csrf') or 'missing'


def login(c, role):
    c.get('/login')
    response=c.post('/login',data={'csrf':token(c),'email':role+'.demo@example.test','password':'DemoPass123!'})
    assert response.status_code==302


def test_login_invalid(client):
    client.get('/login')
    resp=client.post('/login',data={'csrf':token(client),'email':'doctor.demo@example.test','password':'wrong'})
    assert b'Invalid email or password' in resp.data


def test_permissions(client):
    login(client,'patient')
    assert client.get('/patients').status_code==403
    assert client.get('/modules/billing').status_code==403
    assert client.get('/appointments').status_code==200


def test_staff_can_create_patient(client):
    login(client,'staff')
    resp=client.post('/patients',data={'csrf':token(client),'name':'Test Patient Gamma','dob':'2001-01-01','phone':'555-0102'},follow_redirects=True)
    assert b'Test Patient Gamma' in resp.data


def test_csrf_rejected(client):
    login(client,'staff')
    resp=client.post('/patients',data={'name':'Bad','dob':'2000-01-01','phone':'123'})
    assert resp.status_code==400


def test_patient_cannot_book_another_patient(client):
    login(client,'patient')
    with app.app_context():
        doctor=db().execute("SELECT id FROM users WHERE role='physician'").fetchone()['id']
    resp=client.post('/appointments',data={'csrf':token(client),'patient_id':2,'physician_id':doctor,'start_at':'2099-01-01T12:00'})
    assert resp.status_code==403


def test_conflicting_bookings(client):
    login(client,'staff')
    with app.app_context():
        doctor=db().execute("SELECT id FROM users WHERE role='physician'").fetchone()['id']
    payload={'csrf':token(client),'patient_id':1,'physician_id':doctor,'start_at':'2099-01-01T12:00'}
    first=client.post('/appointments',data=payload,follow_redirects=True)
    assert b'Appointment scheduled' in first.data
    second=client.post('/appointments',data=payload,follow_redirects=True)
    assert b'conflicts with an existing' in second.data


def test_billing_admin_only(client):
    login(client,'staff')
    assert client.get('/billing').status_code==403


def test_admin_can_create_synthetic_invoice(client):
    login(client,'admin')
    response=client.post('/billing',data={'csrf':token(client),'patient_id':'1','description':'Synthetic clinic charge','amount':'65.00'},follow_redirects=True)
    assert b'Synthetic clinic charge' in response.data
    assert b'65.00' in response.data


def test_physician_encounter_permissions(client):
    login(client,'patient')
    assert client.get('/encounters').status_code==403


def test_status_workflow(client):
    login(client,'staff')
    with app.app_context():
        physician=db().execute("SELECT id FROM users WHERE role='physician'").fetchone()['id']
    client.post('/appointments',data={'csrf':token(client),'patient_id':'1','physician_id':str(physician),'start_at':'2099-06-01T12:00'})
    with app.app_context():
        apid=db().execute('SELECT id FROM appointments ORDER BY id DESC').fetchone()['id']
    resp=client.post(f'/appointments/{apid}/status',data={'csrf':token(client),'status':'confirmed'})
    assert resp.status_code==302
    assert client.post(f'/appointments/{apid}/status',data={'csrf':token(client),'status':'completed'}).status_code==400
