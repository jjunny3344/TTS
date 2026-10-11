# Supertonic TTS Backend Service

[Supertonic 3](https://github.com/supertone-inc/supertonic) (Supertone의 온디바이스 TTS, 31개 언어, 44.1kHz)을 FastAPI로 감싼 TTS 백엔드 서비스입니다. 모델은 ONNX Runtime으로 CPU에서 프로세스 내 실행됩니다.

## 실행

모델 파일(~385MB)은 `models/supertonic-3/`에 포함되어 있고 Git LFS로 관리됩니다. 클론 전에 Git LFS를 설치하세요 (`git lfs install`).

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

인터넷 연결 없이 실행됩니다 (폐쇄망 가능). 테스트 페이지: http://127.0.0.1:8000/ / API 문서: http://127.0.0.1:8000/docs

## API

| Method | Path | 설명 |
|---|---|---|
| GET | `/health` | 상태 / 모델 정보 (인증 없음) |
| GET | `/v1/voices` | 사용 가능한 보이스 (`F1`–`F5`, `M1`–`M5` + 커스텀) |
| GET | `/v1/languages` | 지원 언어 코드 (`ko`, `en`, `ja`, ... , `na`=자동) |
| POST | `/v1/tts` | 음성 합성 → 오디오 바이너리 반환 |
| POST | `/v1/audio/speech` | OpenAI TTS API 호환 엔드포인트 |

### `POST /v1/tts`

```json
{
  "text": "안녕하세요. 반갑습니다.",
  "voice": "F1",
  "lang": "ko",
  "speed": 1.05,
  "steps": 8,
  "silence": 0.3,
  "response_format": "wav"
}
```

- `text` 외에는 모두 선택값입니다.
- `speed`: 0.7–2.0 / `steps`: 1–50 (높을수록 품질↑, 속도↓) / `response_format`: `wav`, `mp3`, `flac`, `ogg`
- 응답 헤더: `X-Audio-Duration`, `X-Sample-Rate`, `X-Processing-Time`

```bash
curl -X POST http://127.0.0.1:8000/v1/tts -H "content-type: application/json" \
  -d '{"text":"안녕하세요","voice":"F1","lang":"ko"}' -o out.wav

python examples/client.py "안녕하세요" -o out.mp3 --voice M1
```

### OpenAI 호환

기존 OpenAI SDK의 `base_url`만 바꿔 사용할 수 있습니다. `voice`에는 Supertonic 보이스 이름을 사용하고, 언어는 `TTS_DEFAULT_LANG`을 따릅니다.

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="unused")
client.audio.speech.create(model="tts-1", voice="F1", input="안녕하세요").write_to_file("out.mp3")
```

## 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `TTS_MODEL` | `supertonic-3` | `supertonic`(영어), `supertonic-2`, `supertonic-3` |
| `TTS_MODEL_DIR` | `models/<TTS_MODEL>` | 모델 디렉터리 경로 |
| `TTS_AUTO_DOWNLOAD` | `false` | `true`면 모델 파일이 없을 때 HuggingFace에서 다운로드 |
| `TTS_INTRA_OP_THREADS` | 자동 | ONNX Runtime 스레드 수 |
| `TTS_CUSTOM_VOICES_DIR` | - | 커스텀 보이스 JSON 폴더 (파일명 = 보이스 이름) |
| `TTS_DEFAULT_VOICE` | `F1` | 기본 보이스 |
| `TTS_DEFAULT_LANG` | `ko` | 기본 언어 |
| `TTS_MAX_TEXT_CHARS` | `5000` | 요청당 최대 글자 수 |
| `TTS_MAX_CONCURRENCY` | `1` | 동시 합성 작업 수 (초과 요청은 대기) |
| `TTS_API_KEY` | - | 설정 시 `Authorization: Bearer <key>` 필요 |

## 처리 흐름

```
시작:  모델 로딩 → 보이스 준비 → 동시 처리 제한 설정

요청:  인증 → 입력 검사 → 보이스·언어 확인 → 대기 → 합성 → 인코딩 → 응답
```

- **서버 시작 시**: ONNX 모델 4개와 보이스 10개를 한 번만 메모리에 올리고, 동시 합성 수 제한(기본 1)을 설정합니다.
- **`POST /v1/tts` 요청 시**:
  1. 인증(`401`), 입력 검사(`422`), 보이스·언어 확인(`400`)을 차례로 거칩니다.
  2. 차례가 되면 별도 스레드에서 합성하고 요청한 포맷으로 인코딩합니다.
  3. 오디오와 메타 헤더를 함께 응답합니다.
- 처리 시간은 대부분 합성 단계에서 걸리며, `steps`로 속도와 품질을 조절합니다.

자세한 내용은 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)를 참고하세요.

## 테스트

```powershell
.\.venv\Scripts\python -m pytest
```

테스트는 가짜 엔진을 사용하므로 모델 없이 실행됩니다.

## 참고

- 업스트림 Supertonic 저장소는 archive(읽기 전용) 상태입니다. 그래서 `requirements.txt`에서 SDK 버전을 고정합니다.
- 라이선스: 코드 MIT, 모델 OpenRAIL-M.
