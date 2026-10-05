import os
from itertools import count

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, field_validator

APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

app = FastAPI(
    title="Secure CI/CD Notes API",
    description="A small FastAPI application for a DevSecOps portfolio project.",
    version="1.0.0",
)

notes: list[dict[str, object]] = []
note_id_sequence = count(start=1)


class NoteCreate(BaseModel):
    """Request body used to create a note."""

    content: str = Field(
        min_length=1,
        max_length=500,
        examples=["Prepare GitHub Actions security pipeline documentation."],
    )

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        """Reject strings containing only whitespace."""
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("Note content must not be blank.")

        return cleaned_value


class Note(BaseModel):
    """A note returned by the API."""

    id: int
    content: str


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a basic application health status."""
    return {
        "status": "ok",
        "environment": APP_ENV,
        "log_level": LOG_LEVEL,
    }


@app.get("/notes", response_model=list[Note])
def get_notes() -> list[dict[str, object]]:
    """Return all notes currently stored in memory."""
    return notes


@app.post("/notes", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(note: NoteCreate) -> dict[str, object]:
    """Validate and store a new note."""
    if len(notes) >= 100:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Note limit reached. Try again later.",
        )

    new_note: dict[str, object] = {
        "id": next(note_id_sequence),
        "content": note.content,
    }
    notes.append(new_note)

    return new_note
