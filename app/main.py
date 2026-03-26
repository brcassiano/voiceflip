# entry point FastAPI — no business logic here
from fastapi import FastAPI

from app.api.routes import router
from app.store import InMemoryStore

app = FastAPI(title="VoiceFlip Pipeline")

_store = InMemoryStore()


def get_store() -> InMemoryStore:
    return _store


app.include_router(router)
