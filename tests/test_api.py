import io

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.config import Settings
from app.engine import SynthesisResult
from app.main import create_app


class FakeEngine:
    model_name = "fake"
    sample_rate = 44100
    voices = ["F1", "M1"]
    languages = ["en", "ko", "na"]

    def __init__(self, settings):
        self.calls = []

    def synthesize(self, text, voice, lang, speed, steps, silence):
        self.calls.append(dict(text=text, voice=voice, lang=lang, speed=speed, steps=steps))
        audio = np.sin(np.linspace(0, 440 * 2 * np.pi, self.sample_rate)).astype(np.float32) * 0.1
        return SynthesisResult(audio=audio, sample_rate=self.sample_rate, duration=1.0)


def make_client(**overrides):
    settings = Settings(**overrides)
    return TestClient(create_app(settings, engine_factory=FakeEngine))


@pytest.fixture
def client():
    with make_client() as c:
        yield c


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "model": "fake", "sample_rate": 44100}


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_voices_and_languages(client):
    assert client.get("/v1/voices").json()["voices"] == ["F1", "M1"]
    assert "ko" in client.get("/v1/languages").json()["languages"]


@pytest.mark.parametrize("fmt,media", [("wav", "audio/wav"), ("flac", "audio/flac"), ("mp3", "audio/mpeg"), ("ogg", "audio/ogg")])
def test_tts_formats(client, fmt, media):
    r = client.post("/v1/tts", json={"text": "안녕하세요", "response_format": fmt})
    assert r.status_code == 200
    assert r.headers["content-type"] == media
    assert r.headers["x-audio-duration"] == "1.000"
    data, sr = sf.read(io.BytesIO(r.content))
    assert sr == 44100 and len(data) > 40000


def test_tts_defaults_passed_to_engine(client):
    client.post("/v1/tts", json={"text": "hi"})
    call = client.app.state.engine.calls[-1]
    assert call == dict(text="hi", voice="F1", lang="ko", speed=1.05, steps=8)


@pytest.mark.parametrize(
    "body",
    [
        {"text": ""},
        {"text": "   "},
        {"text": "hi", "voice": "nope"},
        {"text": "hi", "lang": "xx"},
        {"text": "hi", "speed": 5},
        {"text": "hi", "response_format": "aac"},
    ],
)
def test_tts_rejects_bad_input(client, body):
    assert client.post("/v1/tts", json=body).status_code in (400, 422)


def test_text_length_limit():
    with make_client(max_text_chars=10) as c:
        assert c.post("/v1/tts", json={"text": "x" * 11}).status_code == 422


def test_openai_compatible(client):
    r = client.post("/v1/audio/speech", json={"model": "tts-1", "input": "hello", "voice": "M1", "speed": 4.0})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert client.app.state.engine.calls[-1]["speed"] == 2.0


def test_api_key():
    with make_client(api_key="secret") as c:
        assert c.post("/v1/tts", json={"text": "hi"}).status_code == 401
        ok = c.post("/v1/tts", json={"text": "hi"}, headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200
        assert c.get("/health").status_code == 200
