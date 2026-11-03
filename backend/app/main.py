from fastapi import FastAPI

app = FastAPI(title="Code Nova - Clinical Management Software")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
