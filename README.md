# OpenClaw Thinking Proxy

A tiny OpenAI-compatible proxy for people using OpenClaw with Qwen Coding Plan endpoints.

It keeps requests as transparent as possible, but **always forces**:

- `stream = true`
- `enable_thinking = true`

This is useful when your client can talk to an OpenAI-compatible endpoint, but does not reliably send `enable_thinking` for Qwen-compatible backends.

## What it does

- Accepts `POST /v1/chat/completions`
- Reads the incoming JSON body
- Forces `stream=true`
- Forces `enable_thinking=true`
- Forwards the rest of the payload with minimal changes
- Returns the upstream response as SSE (`text/event-stream`)

## What it does **not** do

- No search orchestration
- No tool routing
- No prompt rewriting
- No auth layer
- No rate limiting
- No multi-tenant protections

It is intentionally a **thin local compatibility shim**, not a full API gateway.

## Requirements

- Python 3.10+

## Install

```bash
python -m venv .venv
source .venv/bin/activate
# Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Run

By default, it forwards to:

- `https://coding-intl.dashscope.aliyuncs.com/v1`

Start it:

```bash
uvicorn main:app --host 127.0.0.1 --port 4000
```

Or with environment variables:

```bash
export UPSTREAM_BASE_URL="https://coding-intl.dashscope.aliyuncs.com/v1"
export HOST="127.0.0.1"
export PORT="4000"
uvicorn main:app --host "$HOST" --port "$PORT"
```

## Health check

```bash
curl http://127.0.0.1:4000/health
```

Expected response:

```json
{"ok": true, "upstream": "https://coding-intl.dashscope.aliyuncs.com/v1"}
```

## OpenClaw setup

Point your OpenClaw custom provider base URL to:

```text
http://127.0.0.1:4000/v1
```

This proxy only changes the request body enough to force `stream=true` and `enable_thinking=true`.

### Example OpenClaw configuration

Below is a complete example of how to configure the `models` and `agents` sections in your OpenClaw settings to use this proxy with the `bailian` provider:

```json
"models": {
  "mode": "replace",
  "providers": {
    "bailian": {
      "baseUrl": "http://127.0.0.1:4000/v1",
      "apiKey": "__OPENCLAW_REDACTED__",
      "api": "openai-completions",
      "models": [
        {
          "id": "qwen3.5-plus",
          "name": "qwen3.5-plus",
          "api": "openai-completions",
          "reasoning": true,
          "input": ["text", "image"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 1000000,
          "maxTokens": 65536
        },
        {
          "id": "qwen3-max-2026-01-23",
          "name": "qwen3-max-2026-01-23",
          "api": "openai-completions",
          "reasoning": true,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 65536
        },
        {
          "id": "qwen3-coder-next",
          "name": "qwen3-coder-next",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 65536
        },
        {
          "id": "qwen3-coder-plus",
          "name": "qwen3-coder-plus",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 1000000,
          "maxTokens": 65536
        },
        {
          "id": "MiniMax-M2.5",
          "name": "MiniMax-M2.5",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 1000000,
          "maxTokens": 65536
        },
        {
          "id": "glm-5",
          "name": "glm-5",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 202752,
          "maxTokens": 16384
        },
        {
          "id": "glm-4.7",
          "name": "glm-4.7",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 202752,
          "maxTokens": 16384
        },
        {
          "id": "kimi-k2.5",
          "name": "kimi-k2.5",
          "api": "openai-completions",
          "reasoning": false,
          "input": ["text", "image"],
          "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
          "contextWindow": 262144,
          "maxTokens": 32768
        }
      ]
    }
  }
},
"agents": {
  "defaults": {
    "model": {
      "primary": "bailian/qwen3-max-2026-01-23",
      "fallbacks": [
        "bailian/glm-5",
        "bailian/kimi-k2.5"
      ]
    },
    "imageModel": {
      "primary": "bailian/qwen3.5-plus"
    },
    "models": {
      "bailian/qwen3.5-plus": {},
      "bailian/qwen3-max-2026-01-23": {},
      "bailian/qwen3-coder-next": {},
      "bailian/qwen3-coder-plus": {},
      "bailian/MiniMax-M2.5": {},
      "bailian/glm-5": {},
      "bailian/glm-4.7": {},
      "bailian/kimi-k2.5": {}
    }
  }
}
```

## Behavior notes

Because the proxy modifies the JSON body, it cannot preserve the original `Content-Length` header. That header is removed and recalculated by the HTTP client. This is normal and required.

Most headers are passed through unchanged. Only a few transport-level headers are stripped:

- `host`
- `content-length`
- `connection`
- `transfer-encoding`

## Test with curl

```bash
curl -N http://127.0.0.1:4000/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-max-2026-01-23",
    "messages": [
      {"role": "user", "content": "Hello"}
    ]
  }'
```

Even if you do not send `stream` or `enable_thinking`, the proxy will force both.

## Limitations

- This assumes the upstream endpoint is OpenAI-compatible at `/v1/chat/completions`
- This repo is not affiliated with OpenClaw, Alibaba Cloud, or Qwen
- Best used on localhost or a trusted internal network

## Publish to GitHub

Create a new repository, then run:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

## License

MIT
