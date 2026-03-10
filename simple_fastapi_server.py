from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn


app = FastAPI()


class DataPayload(BaseModel):
    data: str  # base64-encoded text


# In-memory storage for latest payloads
agent_data_b64: str | None = None
handler_data_b64: str | None = None


@app.post("/agent/upload")
async def agent_upload(payload: DataPayload):
    global agent_data_b64
    agent_data_b64 = payload.data
    return {"status": "ok"}


@app.post("/handler/upload")
async def handler_upload(payload: DataPayload):
    global handler_data_b64
    handler_data_b64 = payload.data
    return {"status": "ok"}


@app.get("/agent/retrieve-handler")
async def agent_retrieve_handler():
    return {"data": handler_data_b64 or ""}


@app.get("/handler/retrieve-agent")
async def handler_retrieve_agent():
    return {"data": agent_data_b64 or ""}


if __name__ == "__main__":
    uvicorn.run(
        "simple_fastapi_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

