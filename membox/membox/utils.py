
import logging
from dotenv import load_dotenv
import os
from fastapi.responses import FileResponse
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings, save
from iso_language_codes import language_name
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain.chains.llm import LLMChain
from fastapi.responses import JSONResponse
import boto3
import uuid
import tempfile


def download_wav_from_s3(bucket_name: str, object_key: str) -> str:
    s3 = boto3.client("s3")
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    s3.download_fileobj(bucket_name, object_key, temp_file)
    temp_file.close()
    return temp_file.name


def preprocess_text(text: str, role: str, lang: str) -> str:
    load_dotenv(".env")
    gpt_3_5 = init_chat_model("gpt-3.5-turbo", model_provider="openai", temperature=0.7)
    role_prompt = ChatPromptTemplate.from_template(
        """
        You are acting as: {role}
        Respond to this message **as if you were this person**:
        "{question}"
        Only write the answer this person would give.
        """
    )
    role_chain = LLMChain(llm=gpt_3_5, prompt=role_prompt)
    translate_prompt = ChatPromptTemplate.from_template(
        """
    Translate the following text into {language}. Only return the translation, nothing else.

    Text:
    \"\"\"{text}\"\"\"
    """
    )
    translate_chain = LLMChain(llm=gpt_3_5, prompt=translate_prompt)
    answer_as_role = role_chain.run({"role": role, "question": text})
    translated_answer = translate_chain.run(
        {"text": answer_as_role, "language": language_name(lang)}
    )
    print("🧔 Response as Role:\n", answer_as_role)
    print("\n🌍 Translated:\n", translated_answer)
    return translated_answer


def check_voice_id(input_wav: str) -> str:
    client = ElevenLabs(
        api_key=os.environ["ELEVEN_API_KEY"],
    )
    client.voices.get_all()


def analyze_audio_elevenlabs_voice_id(
    voice_id: str, data: dict, text: str
) -> FileResponse:
    """Process and convert audio data using ELEVEN LABS.

    Args:
        data (bytes): The audio data as bytes.
        text (str): The text to be synthesized.
    """
    client = ElevenLabs(
        api_key=os.environ["ELEVEN_API_KEY"],
    )
    voice = client.voices.get(voice_id)
    audio = client.generate(
        text=text,
        voice=voice,
        model="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=1.0, style=0.7),
    )
    output_wav = "/tmp/output.wav"
    logging.info(output_wav)
    save(audio, output_wav)
    logging.info("Finished!")
    logging.info("Sending data...")
    return FileResponse(output_wav)


def analyze_audio_elevenlabs(input_wav: str, data: dict, text: str) -> FileResponse:
    """Process and convert audio data using ELEVEN LABS.

    Args:
        data (bytes): The audio data as bytes.
        text (str): The text to be synthesized.
    """
    client = ElevenLabs(
        api_key=os.environ["ELEVEN_API_KEY"],
    )
    voice = None
    voice_id = data.get("voice_id")
    if not voice_id:
        voice = client.clone(
            name=data["who"],
            description="N/A",  # Optional
            files=[input_wav],
        )
        voice_id = voice.voice_id
    else:
        voice = client.voices.get(voice_id)

    audio = client.generate(
        text=text,
        voice=voice,
        model="eleven_multilingual_v2",
        voice_settings=VoiceSettings(stability=0.5, similarity_boost=1.0, style=0.7),
    )
    output_wav = "/tmp/output.wav"
    logging.info(output_wav)
    save(audio, output_wav)
    logging.info("Finished!")
    s3 = boto3.client("s3")
    key = f"{uuid.uuid4()}.wav"
    bucket = data["bucket"]
    s3.upload_file("/tmp/output.wav", bucket, key)
    return JSONResponse(
        content={
            "statusCode": 200,
            "audio_key": key,
            "voice_id": voice_id,
        }
    )


def get_presigned_url(bucket, key, expires_in=3600):
    s3 = boto3.client("s3")
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )
