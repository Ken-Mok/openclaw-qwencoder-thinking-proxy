import json
import os

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

BASE_URL = os.getenv("UPSTREAM_BASE_URL", "https://coding-intl.dashscope.aliyuncs.com/v1")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "4000"))

app = FastAPI(title="OpenClaw Thinking Proxy")
client: httpx.AsyncClient | None = None

# Keep this proxy as transparent as possible.
# We only strip headers that are unsafe to forward after mutating the body.
STRIP_HEADERS = {"host", "content-length", "connection", "transfer-encoding"}


@app.on_event("startup")
async def startup() -> None:
    global client
    client = httpx.AsyncClient(
        limits=httpx.Limits(max_connections=500, max_keepalive_connections=100),
        timeout=httpx.Timeout(connect=10.0, read=None, write=30.0, pool=10.0),
    )


@app.on_event("shutdown")
async def shutdown() -> None:
    global client
    if client:
        await client.aclose()


@app.get("/health")
async def health() -> dict[str, object]:
    return {"ok": True, "upstream": BASE_URL}


@app.post("/v1/chat/completions")
async def passthrough(req: Request) -> StreamingResponse:
    """
    Thin compatibility proxy for OpenAI-compatible chat completions.

    Behavior:
    - Forces stream=true
    - Forces enable_thinking=true
    - Keeps the rest of the JSON payload as-is
    - Forwards headers with minimal changes
    """
    assert client is not None

    raw_body = await req.body()

    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Request body is not valid JSON") from exc

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object")

    # Force the two flags that OpenClaw may not reliably send.
    body["stream"] = True
    body["enable_thinking"] = True

    patched_body = json.dumps(
        body,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    fwd_headers = dict(req.headers)
    for header_name in STRIP_HEADERS:
        fwd_headers.pop(header_name, None)

    async def gen():
        assert client is not None
        async with client.stream(
            "POST",
            f"{BASE_URL}/chat/completions",
            headers=fwd_headers,
            content=patched_body,
        ) as resp:
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                detail = await resp.aread()
                message = detail.decode("utf-8", errors="ignore")
                error_payload = {"error": message, "status_code": resp.status_code}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n".encode("utf-8")
                return

            async for chunk in resp.aiter_bytes():
                yield chunk

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
