import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import anyio
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.config import Settings
from app.engine import AudioFormat, TTSEngine, encode_audio

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("tts")

STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Settings | None = None, engine_factory=TTSEngine) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Model loading is slow (seconds); do it once in a worker thread.
        app.state.engine = await anyio.to_thread.run_sync(engine_factory, settings)
        app.state.limiter = anyio.CapacityLimiter(settings.max_concurrency)
        yield

    app = FastAPI(title="Supertonic TTS Service", version="1.0.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    def require_api_key(
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ) -> None:
        if settings.api_key and (creds is None or creds.credentials != settings.api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    def get_engine(request: Request) -> TTSEngine:
        return request.app.state.engine

    Engine = Annotated[TTSEngine, Depends(get_engine)]

    class TTSRequest(BaseModel):
        text: str = Field(min_length=1, max_length=settings.max_text_chars)
        voice: str = settings.default_voice
        lang: str = settings.default_lang
        speed: float = Field(1.05, ge=0.7, le=2.0)
        steps: int = Field(8, ge=1, le=50, description="Denoising steps: higher = better quality, slower")
        silence: float = Field(0.3, ge=0.0, le=2.0, description="Silence between text chunks (s)")
        response_format: AudioFormat = AudioFormat.wav

    class OpenAISpeechRequest(BaseModel):
        model: str | None = None
        input: str = Field(min_length=1, max_length=settings.max_text_chars)
        voice: str = settings.default_voice
        response_format: AudioFormat = AudioFormat.mp3
        speed: float = Field(1.0, ge=0.25, le=4.0)

    async def synthesize(request: Request, engine: TTSEngine, req: TTSRequest) -> Response:
        if req.voice not in engine.voices:
            raise HTTPException(400, f"Unknown voice '{req.voice}'. Available: {engine.voices}")
        if req.lang not in engine.languages:
            raise HTTPException(400, f"Unsupported lang '{req.lang}'. Available: {engine.languages}")
        if not req.text.strip():
            raise HTTPException(400, "Text must not be blank")

        def work():
            result = engine.synthesize(
                req.text, req.voice, req.lang, req.speed, req.steps, req.silence
            )
            return result, *encode_audio(result, req.response_format)

        started = time.perf_counter()
        result, audio, media_type = await anyio.to_thread.run_sync(
            work, limiter=request.app.state.limiter
        )
        elapsed = time.perf_counter() - started
        logger.info(
            "tts chars=%d voice=%s lang=%s audio=%.2fs took=%.2fs",
            len(req.text), req.voice, req.lang, result.duration, elapsed,
        )
        return Response(
            content=audio,
            media_type=media_type,
            headers={
                "X-Audio-Duration": f"{result.duration:.3f}",
                "X-Sample-Rate": str(result.sample_rate),
                "X-Processing-Time": f"{elapsed:.3f}",
            },
        )

    @app.get("/", include_in_schema=False)
    def index():
        """
        테스트 페이지: 브라우저에서 텍스트를 입력해 합성하고 바로 재생
        """
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health(engine: Engine):
        """
        헬스 체크: 서비스 상태와 로드된 모델 정보 반환
        (인증 불필요, 로드밸런서/모니터링용)
        """
        return {"status": "ok", "model": engine.model_name, "sample_rate": engine.sample_rate}

    @app.get("/v1/voices", dependencies=[Depends(require_api_key)])
    def list_voices(engine: Engine):
        """
        보이스 목록: 내장 보이스(F1–F5, M1–M5)와 커스텀 보이스 이름, 기본 보이스 반환
        """
        return {"voices": engine.voices, "default": settings.default_voice}

    @app.get("/v1/languages", dependencies=[Depends(require_api_key)])
    def list_languages(engine: Engine):
        """
        언어 목록: 모델이 지원하는 언어 코드("na"는 언어 자동 처리)와 기본 언어 반환
        """
        return {"languages": engine.languages, "default": settings.default_lang}

    @app.post(
        "/v1/tts",
        dependencies=[Depends(require_api_key)],
        response_class=Response,
        responses={200: {"content": {"audio/wav": {}, "audio/mpeg": {}, "audio/flac": {}, "audio/ogg": {}}}},
    )
    async def tts(request: Request, engine: Engine, body: TTSRequest):
        """
        음성 합성: 텍스트를 보이스/언어/속도/품질(steps) 옵션으로 합성해 오디오 바이너리로 반환
        응답 헤더에 오디오 길이(X-Audio-Duration)와 처리 시간(X-Processing-Time) 포함
        """
        return await synthesize(request, engine, body)

    @app.post(
        "/v1/audio/speech",
        dependencies=[Depends(require_api_key)],
        response_class=Response,
        summary="OpenAI-compatible speech endpoint",
    )
    async def openai_speech(request: Request, engine: Engine, body: OpenAISpeechRequest):
        """
        OpenAI 호환 음성 합성: OpenAI TTS API 요청 형식(model/input/voice)을 받아 /v1/tts와 동일하게 처리
        기존 OpenAI SDK에서 base_url만 바꿔 사용 가능
        """
        # OpenAI has no lang field; use the default and clamp speed to Supertonic's range.
        req = TTSRequest(
            text=body.input,
            voice=body.voice,
            speed=min(max(body.speed, 0.7), 2.0),
            response_format=body.response_format,
        )
        return await synthesize(request, engine, req)

    return app


app = create_app()
