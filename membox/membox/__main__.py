
import utils
import uvicorn
from fastapi import FastAPI, Form
from pydantic import BaseModel, Json
from dotenv import load_dotenv
from mangum import Mangum
import logging
load_dotenv()

app = FastAPI()

handler = Mangum(app)


class Data(BaseModel):
    who: str
    text: str
    lang: str


@app.get("/")
async def enhance_audio() -> dict:
    return {"audio": "enhanced"}


@app.post("/tts")
async def tts(data: Json = Form()):
    load_dotenv()
    logging.info("Received audio file...")
    logging.info(data)
    wav_path = utils.download_wav_from_s3(data["bucket"], data["key"])
    logging.info(f"input_wav path: {wav_path}")
    logging.info(f"Translating from {data['text']}")
    text = utils.preprocess_text(data["text"], data["rs"], data["lang"])
    return utils.analyze_audio_elevenlabs(str(wav_path), data, text)


def main():
    """_summary_"""
    load_dotenv()
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()