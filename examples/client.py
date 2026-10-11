"""Example client: python examples/client.py "안녕하세요" -o out.wav --voice F1 --lang ko"""
import argparse
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("-o", "--output", default="output.wav")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--voice", default="F1")
    parser.add_argument("--lang", default="ko")
    parser.add_argument("--speed", type=float, default=1.05)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--format", default=None, help="wav|mp3|flac|ogg (default: from output extension)")
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    fmt = args.format or args.output.rsplit(".", 1)[-1]
    headers = {"Authorization": f"Bearer {args.api_key}"} if args.api_key else {}
    resp = httpx.post(
        f"{args.url}/v1/tts",
        json={
            "text": args.text,
            "voice": args.voice,
            "lang": args.lang,
            "speed": args.speed,
            "steps": args.steps,
            "response_format": fmt,
        },
        headers=headers,
        timeout=300,
    )
    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}", file=sys.stderr)
        return 1

    with open(args.output, "wb") as f:
        f.write(resp.content)
    print(
        f"Saved {args.output}: {resp.headers['x-audio-duration']}s audio, "
        f"generated in {resp.headers['x-processing-time']}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
