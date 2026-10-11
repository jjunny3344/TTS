# 서버 실행 / 종료

## 실행

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 모델 로딩에 몇 초 걸립니다. 로그에 `Application startup complete.`가 나오면 준비된 것입니다.
- 테스트 페이지: http://127.0.0.1:8000/ / API 문서: http://127.0.0.1:8000/docs
- 인터넷 연결 없이 실행됩니다 (폐쇄망 가능).

| 옵션 | 설명 |
|---|---|
| `--host 0.0.0.0` | 다른 PC에서도 접속 가능 |
| `--host 127.0.0.1` | 같은 PC에서만 접속 가능 (외부 차단) |
| `--port 8000` | 사용할 포트 |
| `--reload` | 코드 변경 시 자동 재시작 (개발용) |

## 종료

- 서버를 실행한 터미널에서 `Ctrl + C`
- 터미널을 이미 닫았거나 백그라운드로 실행 중이라면, 8000번 포트를 쓰는 프로세스를 종료합니다.

  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
  ```

## venv 활성화 / 해제 (선택)

venv는 프로젝트 전용 Python 환경입니다. 위 명령처럼 `.\.venv\Scripts\python`으로 직접 실행하면 활성화할 필요가 없습니다.

활성화해서 쓰면 `python`, `uvicorn`, `pytest`를 경로 없이 바로 실행할 수 있습니다.

```powershell
.\.venv\Scripts\Activate.ps1   # 활성화 → 프롬프트 앞에 (.venv) 표시
uvicorn app.main:app --port 8000
deactivate                     # 해제 (터미널을 닫아도 해제됨)
```

`Activate.ps1` 실행 시 "스크립트를 실행할 수 없습니다" 오류가 나면 아래 명령을 한 번 실행한 뒤 다시 시도하세요.

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```
