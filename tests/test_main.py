from itertools import count

import pytest
from fastapi.testclient import TestClient

import app.main as main

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def reset_notes() -> None:
    """Reset in-memory application data before every test."""
    main.notes.clear()
    main.note_id_sequence = count(start=1)


def test_health_check_returns_application_status() -> None:
    """The health endpoint should confirm that the API is available."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "environment": "development",
        "log_level": "INFO",
    }


def test_get_notes_returns_empty_list_for_new_application_state() -> None:
    """A clean application state should not contain notes."""
    response = client.get("/notes")

    assert response.status_code == 200
    assert response.json() == []


def test_create_note_and_return_it_in_notes_list() -> None:
    """A valid note should be created and then returned by GET /notes."""
    create_response = client.post(
        "/notes",
        json={"content": "Write automated API tests."},
    )

    assert create_response.status_code == 201
    assert create_response.json() == {
        "id": 1,
        "content": "Write automated API tests.",
    }

    list_response = client.get("/notes")

    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "id": 1,
            "content": "Write automated API tests.",
        }
    ]


def test_create_note_rejects_blank_content() -> None:
    """Whitespace-only content must be rejected by API validation."""
    response = client.post("/notes", json={"content": "   "})

    assert response.status_code == 422
    assert "Note content must not be blank." in response.text
