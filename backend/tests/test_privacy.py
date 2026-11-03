import logging

import pytest

pytestmark = pytest.mark.anyio


async def test_request_access_and_asgi_trace_logging_disabled(client, caplog):
    marker = "synthetic-sensitive-request-marker"
    for name in ("uvicorn.access", "uvicorn.asgi"):
        with caplog.at_level(logging.DEBUG, logger=name):
            logger = logging.getLogger(name)
            assert logger.disabled
            logger.info("/api/patients?q=%s", marker)
    assert marker not in caplog.text


async def test_sql_parameters_are_hidden(client, migrated_database):
    assert migrated_database.engine.hide_parameters is True
    assert logging.getLogger("sqlalchemy.engine").getEffectiveLevel() >= logging.WARNING


async def test_unexpected_error_does_not_log_patient_or_authentication_data(
    client, headers_for, patient_payload, monkeypatch, caplog
):
    headers = headers_for()
    sensitive_error = " ".join([
        patient_payload["first_name"], patient_payload["address"],
        patient_payload["contact_email"], headers["Authorization"],
    ])

    def fail_with_sensitive_error():
        raise RuntimeError(sensitive_error)

    monkeypatch.setattr("app.patients.uuid4", fail_with_sensitive_error)
    with caplog.at_level(logging.ERROR, logger="app.privacy"):
        response = await client.post("/api/patients", json=patient_payload, headers=headers)
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["cache-control"] == "no-store"
    assert "sensitive error details suppressed" in caplog.text
    for value in (patient_payload["address"], patient_payload["contact_email"], headers["Authorization"]):
        assert value not in caplog.text
        assert value not in response.text
    assert all(record.exc_info is None for record in caplog.records)
