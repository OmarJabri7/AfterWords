# cleanup_session.py
import os, json, time
from typing import Iterable, List
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from elevenlabs import ElevenLabs

load_dotenv()

DDB_TABLE = os.environ.get("LEASES_TABLE", "leases")  # set in TF env
ELEVEN_API_KEY = os.environ["ELEVEN_API_KEY"]  # set in TF env

dynamodb = boto3.resource("dynamodb")
leases = dynamodb.Table(DDB_TABLE)

client = ElevenLabs(api_key=ELEVEN_API_KEY)


def _as_list(x) -> List[str]:
    if x is None:
        return []
    if isinstance(x, str):
        return [x]
    if isinstance(x, Iterable):
        return [str(i) for i in x]
    return []


def delete_voices(voice_ids: List[str]):
    deleted, failed = [], {}
    for vid in set(voice_ids):  # dedupe
        if not vid:
            continue
        try:
            client.voices.delete(voice_id=vid)
            deleted.append(vid)
        except Exception as e:
            failed[vid] = str(e)
    return deleted, failed


def delete_lease(session_id: str):
    if not session_id:
        return {"deleted": False, "reason": "no_session_id"}
    try:
        # Idempotent: delete if exists
        leases.delete_item(Key={"session_id": session_id})
        return {"deleted": True}
    except ClientError as e:
        return {"deleted": False, "reason": e.response["Error"]["Message"]}


def handler(event, _context):
    """
    Expected event shape from EventBridge Scheduler (your UI sets this):
    {
      "session_id": "sess_123",           # or "lease_id"
      "voice_ids": ["v1", "v2", ...],     # optional; can also be a single string "voice_id"
      "due_epoch": 1725600000             # optional – informational
    }
    """
    # Accept both keys
    session_id = event.get("session_id") or event.get("lease_id")
    voice_ids = _as_list(event.get("voice_ids") or event.get("voice_id"))

    # 1) Delete ElevenLabs voices (if provided)
    deleted, failed = delete_voices(voice_ids)

    # 2) Delete/cleanup the lease row in DynamoDB
    lease_res = delete_lease(session_id)

    return {
        "ok": True,
        "session_id": session_id,
        "elevenlabs": {"deleted": deleted, "failed": failed},
        "lease": lease_res,
        "ts": int(time.time()),
    }
