import os
import traceback
import tempfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from embed import embed_data
from extract import extract_data

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST"],
    allow_headers=["*"],
)


@app.post("/encode")
async def encode(
    video: UploadFile = File(...),
    message: str = Form(...),
    password: str = Form(...),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
        tmp_in.write(await video.read())
        tmp_in_path = tmp_in.name

    tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp_out.close()

    try:
        embed_data(tmp_in_path, message.encode(), password, tmp_out.name)
        return FileResponse(tmp_out.name, media_type="video/mp4", filename="stego_video.mp4")
    finally:
        os.unlink(tmp_in_path)


@app.post("/decode")
async def decode(
    video: UploadFile = File(...),
    password: str = Form(...),
):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_in:
        tmp_in.write(await video.read())
        tmp_in_path = tmp_in.name

    try:
        data = extract_data(tmp_in_path, password)
        return {"message": data.decode()}
    except Exception as e:
        traceback.print_exc()  # full trace visible in the uvicorn server console
        if "No hidden data" in str(e):
            detail = "No hidden data found in this video"
        else:
            detail = "Wrong password or corrupted payload"
        raise HTTPException(status_code=400, detail=detail)
    finally:
        os.unlink(tmp_in_path)
