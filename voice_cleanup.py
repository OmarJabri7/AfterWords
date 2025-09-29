import json, time, os
from elevenlabs import ElevenLabs
from dotenv import load_dotenv

load_dotenv()
TIMEOUT = 10 * 60


def should_cleanup():
    try:
        with open("session_state.json") as f:
            data = json.load(f)
        return (time.time() - data["last_activity"]) > TIMEOUT
    except:
        return False


def delete_voice():
    client = ElevenLabs(api_key=os.getenv("ELEVEN_API_KEY"))
    voices = client.voices.get_all().voices
    for v in voices:
        try:
            client.voices.delete(voice_id=v.voice_id)
            print(f"✅ Deleted {v.voice_id}")
        except Exception as e:
            print(f"❌ Failed {v.voice_id}: {e}")


if __name__ == "__main__":
    while True:
        if should_cleanup():
            print("⏰ Cleaning up inactive session...")
            delete_voice()
            os.remove("session_state.json")  # optional
        time.sleep(30)  # check every 30s
