from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.models import Patient, Role

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("role", ["administrator", "clinic_staff"])
async def test_create_patient(client, headers_for, patient_payload, migrated_database, role):
    response = await client.post("/api/patients", json=patient_payload, headers=headers_for(role))
    assert response.status_code == 201
    body = response.json()
    assert set(body) == set(patient_payload) | {"patient_id", "created_at", "updated_at"}
    assert UUID(body["patient_id"]).version == 4
    for field, value in patient_payload.items():
        assert body[field] == value
    for field in ("created_at", "updated_at"):
        assert datetime.fromisoformat(body[field].replace("Z", "+00:00")).tzinfo is not None
    assert response.headers["location"] == f"/api/patients/{body['patient_id']}"
    assert response.headers["cache-control"] == "no-store"
    with migrated_database.SessionLocal() as session:
        assert session.get(Patient, UUID(body["patient_id"])).first_name == "Casey"


async def test_identical_demographics_have_distinct_ids(client, headers_for, patient_payload):
    headers = headers_for()
    first = await client.post("/api/patients", json=patient_payload, headers=headers)
    second = await client.post("/api/patients", json=patient_payload, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["patient_id"] != second.json()["patient_id"]


async def test_required_fields_and_unicode_names(client, headers_for):
    response = await client.post(
        "/api/patients", headers=headers_for(),
        json={
            "first_name": "  Zoë  ", "last_name": "O’Example-Smith",
            "date_of_birth": datetime.now(timezone.utc).date().isoformat(),
        },
    )
    assert response.status_code == 201
    assert response.json()["first_name"] == "Zoë"
    assert response.json()["contact_email"] is None
    assert response.json()["phone_number"] is None
    assert response.json()["address"] is None


@pytest.mark.parametrize("role", ["administrator", "clinic_staff", "physician", "patient"])
@pytest.mark.parametrize("operation", ["create", "list", "search", "get", "patch"])
async def test_role_permissions(
    client, headers_for, patient_factory, patient_payload, migrated_database, role, operation
):
    patient = patient_factory()
    path = f"/api/patients/{patient.patient_id}"
    headers = headers_for(role)
    if operation == "create":
        response = await client.post("/api/patients", json=patient_payload, headers=headers)
    elif operation == "list":
        response = await client.get("/api/patients", headers=headers)
    elif operation == "search":
        response = await client.get("/api/patients", params={"q": "Casey"}, headers=headers)
    elif operation == "get":
        response = await client.get(path, headers=headers)
    else:
        response = await client.patch(path, json={"first_name": "Updated"}, headers=headers)

    permitted = role in ("administrator", "clinic_staff") or (
        role == "physician" and operation in ("list", "search", "get")
    )
    expected = (201 if operation == "create" else 200) if permitted else 403
    assert response.status_code == expected
    assert response.headers["cache-control"] == "no-store"
    if not permitted:
        assert response.json() == {"detail": "Insufficient permissions"}
        assert patient.first_name not in response.text
        with migrated_database.SessionLocal() as session:
            assert session.scalar(select(func.count()).select_from(Patient)) == 1
            assert session.get(Patient, patient.patient_id).first_name == patient.first_name


@pytest.mark.parametrize("operation", ["create", "list", "search", "get", "patch"])
async def test_unauthenticated_access(client, patient_factory, patient_payload, operation):
    patient = patient_factory()
    if operation == "create":
        response = await client.post("/api/patients", json=patient_payload)
    elif operation in ("list", "search"):
        response = await client.get("/api/patients", params={"q": "Casey"} if operation == "search" else {})
    elif operation == "get":
        response = await client.get(f"/api/patients/{patient.patient_id}")
    else:
        response = await client.patch(
            f"/api/patients/{patient.patient_id}", json={"first_name": "Changed"}
        )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert patient.contact_email not in response.text


async def test_inactive_account_cannot_access_patients(client, account_factory, signed_token):
    user = account_factory("inactive.reader@example.com", Role.ADMINISTRATOR, is_active=False)
    response = await client.get(
        "/api/patients", headers={"Authorization": f"Bearer {signed_token(user.id)}"}
    )
    assert response.status_code == 401


async def test_matching_email_does_not_grant_self_service(
    client, account_factory, signed_token, patient_factory
):
    patient = patient_factory()
    user = account_factory(patient.contact_email, Role.PATIENT)
    headers = {"Authorization": f"Bearer {signed_token(user.id)}"}
    for patient_id in (patient.patient_id, uuid4()):
        response = await client.get(f"/api/patients/{patient_id}", headers=headers)
        assert response.status_code == 403


async def test_retrieve_patient(client, headers_for, patient_factory):
    patient = patient_factory()
    response = await client.get(f"/api/patients/{patient.patient_id}", headers=headers_for())
    assert response.status_code == 200
    assert response.json()["patient_id"] == str(patient.patient_id)
    assert response.json()["contact_email"] == patient.contact_email
    assert "user_id" not in response.json()


@pytest.mark.parametrize("query", ["casey", "EXAMPLE", "Casey Example", "  Casey  ", "id", "upper_id"])
async def test_search_by_name_or_id(client, headers_for, patient_factory, query):
    first = patient_factory()
    last_name_match = patient_factory(first_name="Riley")
    patient_factory(first_name="Jordan", last_name="Sample")
    search = str(first.patient_id) if query in ("id", "upper_id") else query
    if query == "upper_id":
        search = search.upper()
    response = await client.get("/api/patients", params={"q": search}, headers=headers_for())
    assert response.status_code == 200
    expected = {str(first.patient_id)}
    if query == "EXAMPLE":
        expected.add(str(last_name_match.patient_id))
    assert {item["patient_id"] for item in response.json()["items"]} == expected
    assert response.json()["total"] == len(expected)


@pytest.mark.parametrize("query", ["NoMatch", "%", "_", "%' OR 1=1 --"])
async def test_search_does_not_expand_wildcards_or_sql(client, headers_for, patient_factory, query):
    patient_factory()
    response = await client.get("/api/patients", params={"q": query}, headers=headers_for())
    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


async def test_search_escapes_literal_percent(client, headers_for, patient_factory):
    match = patient_factory(last_name="Percent%Example")
    patient_factory()
    response = await client.get("/api/patients", params={"q": "%"}, headers=headers_for())
    assert response.status_code == 200
    assert [item["patient_id"] for item in response.json()["items"]] == [str(match.patient_id)]


async def test_empty_directory(client, headers_for):
    response = await client.get("/api/patients", headers=headers_for())
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


async def test_pagination_defaults_limits_and_total(client, headers_for, patient_factory):
    patients = [patient_factory(last_name=f"Example {index:02}") for index in range(23)]
    headers = headers_for()
    response = await client.get("/api/patients", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 23
    assert response.json()["limit"] == 20
    assert response.json()["offset"] == 0
    assert len(response.json()["items"]) == 20
    response = await client.get("/api/patients", params={"limit": 10, "offset": 20}, headers=headers)
    assert response.status_code == 200
    assert [item["patient_id"] for item in response.json()["items"]] == [str(p.patient_id) for p in patients[20:]]
    response = await client.get("/api/patients", params={"limit": 100, "offset": 100}, headers=headers)
    assert response.json() == {"items": [], "total": 23, "limit": 100, "offset": 100}
    response = await client.get("/api/patients", params={"q": "Example 0", "limit": 2, "offset": 2}, headers=headers)
    assert response.json()["total"] == 10
    assert [item["patient_id"] for item in response.json()["items"]] == [str(p.patient_id) for p in patients[2:4]]


async def test_pagination_is_stable_for_identical_names(client, headers_for, patient_factory):
    patients = [patient_factory() for _ in range(4)]
    headers = headers_for()
    first = await client.get("/api/patients", params={"limit": 2}, headers=headers)
    second = await client.get("/api/patients", params={"limit": 2, "offset": 2}, headers=headers)
    ids = [item["patient_id"] for item in first.json()["items"] + second.json()["items"]]
    assert ids == sorted(str(patient.patient_id) for patient in patients)


@pytest.mark.parametrize("params", [
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "invalid"},
    {"offset": -1}, {"offset": 1_000_001}, {"offset": "invalid"},
    {"q": ""}, {"q": "   "}, {"q": "x" * 202}, {"q": "Casey\nExample"},
])
async def test_invalid_pagination_and_search(client, headers_for, params):
    response = await client.get("/api/patients", params=params, headers=headers_for())
    assert response.status_code == 422


@pytest.mark.parametrize("role", ["administrator", "clinic_staff"])
async def test_partial_update_preserves_unsupplied_fields(
    client, headers_for, patient_factory, role
):
    patient = patient_factory()
    response = await client.patch(
        f"/api/patients/{patient.patient_id}", headers=headers_for(role),
        json={"first_name": "Changed", "contact_email": "NEW.PATIENT@EXAMPLE.COM"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Changed"
    assert body["contact_email"] == "new.patient@example.com"
    assert body["last_name"] == patient.last_name
    assert body["phone_number"] == patient.phone_number
    assert body["address"] == patient.address
    assert body["date_of_birth"] == patient.date_of_birth.isoformat()
    created = datetime.fromisoformat(body["created_at"].replace("Z", "+00:00"))
    updated = datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00"))
    assert created == patient.created_at.replace(tzinfo=timezone.utc)
    assert updated > patient.updated_at.replace(tzinfo=timezone.utc)


async def test_optional_contact_fields_can_be_cleared(client, headers_for, patient_factory):
    patient = patient_factory()
    changes = {"contact_email": None, "phone_number": None, "address": None}
    response = await client.patch(
        f"/api/patients/{patient.patient_id}", json=changes, headers=headers_for()
    )
    assert response.status_code == 200
    assert all(response.json()[field] is None for field in changes)


@pytest.mark.parametrize("changes", [
    {}, {"first_name": None}, {"last_name": None}, {"date_of_birth": None},
    {"patient_id": str(uuid4())}, {"created_at": "2020-01-01T00:00:00Z"},
    {"updated_at": "2020-01-01T00:00:00Z"}, {"user_id": 1},
    {"first_name": "Changed", "date_of_birth": "9999-01-01"},
    {"phone_number": "invalid"}, {"address": ""},
])
async def test_invalid_updates_are_rejected_atomically(
    client, headers_for, patient_factory, migrated_database, changes
):
    patient = patient_factory()
    response = await client.patch(
        f"/api/patients/{patient.patient_id}", json=changes, headers=headers_for()
    )
    assert response.status_code == 422
    with migrated_database.SessionLocal() as session:
        stored = session.get(Patient, patient.patient_id)
        assert stored.first_name == patient.first_name
        assert stored.date_of_birth == patient.date_of_birth


@pytest.mark.parametrize(("field", "value"), [
    ("first_name", ""), ("first_name", "  "), ("first_name", "x" * 101),
    ("first_name", 123), ("first_name", None), ("first_name", "123"),
    ("first_name", "Casey\x00Example"), ("last_name", ""),
    ("date_of_birth", "9999-01-01"), ("date_of_birth", "2000-02-30"),
    ("date_of_birth", "01/02/1990"), ("date_of_birth", "1990-01-02T00:00:00"),
    ("date_of_birth", 0), ("date_of_birth", None),
    ("contact_email", "invalid-email"), ("contact_email", "x" * 255 + "@example.com"),
    ("phone_number", ""), ("phone_number", "9405550101"),
    ("phone_number", "+0" + "1" * 10), ("phone_number", "+1" + "2" * 15),
    ("address", "  "), ("address", "x" * 501), ("address", "one\ntwo"),
    ("patient_id", str(uuid4())), ("user_id", 1), ("role", "administrator"),
])
async def test_invalid_patient_input(
    client, headers_for, patient_payload, migrated_database, field, value
):
    response = await client.post(
        "/api/patients", json=patient_payload | {field: value}, headers=headers_for()
    )
    assert response.status_code == 422
    assert patient_payload["address"] not in response.text
    assert all("input" not in error for error in response.json()["detail"])
    with migrated_database.SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Patient)) == 0


@pytest.mark.parametrize("field", ["first_name", "last_name", "date_of_birth"])
async def test_missing_required_patient_input(client, headers_for, patient_payload, field):
    patient_payload.pop(field)
    response = await client.post("/api/patients", json=patient_payload, headers=headers_for())
    assert response.status_code == 422


@pytest.mark.parametrize("method", ["GET", "PATCH"])
async def test_missing_patient(client, headers_for, method):
    kwargs = {"json": {"first_name": "Changed"}} if method == "PATCH" else {}
    response = await client.request(
        method, f"/api/patients/{uuid4()}", headers=headers_for(), **kwargs
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Patient not found"}


@pytest.mark.parametrize("identifier", ["123", "not-a-uuid", "00000000-0000-1000-8000-000000000000"])
async def test_invalid_patient_id(client, headers_for, identifier):
    response = await client.get(f"/api/patients/{identifier}", headers=headers_for())
    assert response.status_code == 422


async def test_duplicate_identifier_is_conflict_and_does_not_overwrite(
    client, headers_for, patient_factory, patient_payload, migrated_database, monkeypatch
):
    original = patient_factory()
    headers = headers_for()
    with monkeypatch.context() as patch:
        patch.setattr("app.patients.uuid4", lambda: original.patient_id)
        response = await client.post(
            "/api/patients", json=patient_payload | {"first_name": "Other"}, headers=headers
        )
    assert response.status_code == 409
    assert response.json() == {"detail": "Patient identifier already exists"}
    with migrated_database.SessionLocal() as session:
        assert session.scalar(select(func.count()).select_from(Patient)) == 1
        assert session.get(Patient, original.patient_id).first_name == original.first_name
    response = await client.post("/api/patients", json=patient_payload, headers=headers)
    assert response.status_code == 201
