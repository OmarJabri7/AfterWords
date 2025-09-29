import streamlit as st
from streamlit.components.v1 import html
import requests
import json
import boto3
import uuid
import os
import time
import datetime as dt
from dotenv import load_dotenv
from typing import Any, Dict, Optional

# ================= App constants =================
APP_TITLE = "After Words, the words of the here after."
LAMBDA_BASE = "https://ape2rb6shmlwbcvtchqvhaenai0pjfsr.lambda-url.us-east-2.on.aws"
LAMBDA_TTS = f"{LAMBDA_BASE}/tts"

S3_BUCKET = "after_words-wavs"
REGION = os.getenv("AWS_REGION", "us-east-2")

# EventBridge Scheduler config (server-side cleanup)
SCHEDULER_GROUP = os.getenv("SCHEDULER_GROUP", "after_words-session-schedules")
SCHEDULER_ROLE_ARN = os.getenv(
    "SCHEDULER_ROLE_ARN"
)  # arn:aws:iam::...:role/after_words-scheduler-invoke-cleanup
CLEANUP_LAMBDA_ARN = os.getenv(
    "CLEANUP_LAMBDA_ARN"
)  # arn:aws:lambda:us-east-2:...:function:lambda_cleanup
DEFAULT_TTL = 600  # 10 minutes

# DynamoDB table (reusing your existing "leases" table)
LEASES_TABLE = os.getenv("LEASES_TABLE", "leases")

# ================= Streamlit app config =================
st.set_page_config(layout="centered", page_title=APP_TITLE)
st.title(APP_TITLE)
load_dotenv()

# AWS clients
s3 = boto3.client(
    "s3",
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
)
sch = boto3.client(
    "scheduler",
    region_name=REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
)
ddb = boto3.resource("dynamodb", region_name=REGION)
leases_tbl = ddb.Table(LEASES_TABLE)


# ================= URL session id (sid) =================
def get_or_create_sid() -> Optional[str]:
    """
    If an 'sid' is present in the query params, return it.
    Otherwise return None (we'll set sid only when the user clicks Start Chat).
    """
    params = st.query_params
    if "sid" in params and params["sid"]:
        return params["sid"]
    return None


def set_sid_in_url(session_id: str):
    st.query_params["sid"] = session_id


SID = get_or_create_sid()


# ================= Helpers: DynamoDB (leases) =================
def put_lease_item(
    session_id: str,
    voice_id: Optional[str],
    who: str,
    rs: str,
    lang: str,
    audio_key: str,
    chat_log: list,
    started_at: int,
    expires_at: int,
    status: str = "active",
):
    item = {
        "session_id": session_id,  # PK
        "el_voice_id": voice_id,  # voice id at this moment
        "started_at_epoch": int(started_at),
        "expires_at_epoch": int(expires_at),
        "status": status,  # "active" | "ended" | "expired"
        # Extra (schemaless)
        "who": who,
        "rs": rs,
        "lang": lang,
        "audio_key": audio_key,
        "chat_log": chat_log,
    }
    leases_tbl.put_item(Item=item)


def get_lease(session_id: str) -> Dict[str, Any]:
    resp = leases_tbl.get_item(Key={"session_id": session_id})
    return resp.get("Item", {}) or {}


def update_lease_fields(session_id: str, fields: Dict[str, Any]):
    """
    Generic SET update for arbitrary fields.
    """
    if not fields:
        return
    # Build UpdateExpression dynamically
    names = {}
    values = {}
    sets = []
    for i, (k, v) in enumerate(fields.items(), start=1):
        nk = f"#n{i}"
        vk = f":v{i}"
        names[nk] = k
        values[vk] = v
        sets.append(f"{nk} = {vk}")
    expr = "SET " + ", ".join(sets)
    leases_tbl.update_item(
        Key={"session_id": session_id},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def mark_lease_status(session_id: str, new_status: str):
    update_lease_fields(session_id, {"status": new_status})


# ================= Local UI helpers =================
def fetch_audio_bytes(key: str) -> bytes:
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return obj["Body"].read()


def seconds_left() -> Optional[int]:
    exp = st.session_state.get("expires_at")
    if not exp:
        return None
    return max(0, int(exp) - int(time.time()))


def end_session_local(reason: str):
    st.session_state.session_started = False
    # don't nuke transcript
    st.toast(f"Session ended: {reason}", icon="🛑")
    # reflect in DDB (if we have a lease)
    if st.session_state.get("session_id"):
        mark_lease_status(st.session_state["session_id"], "ended")


# ================= EventBridge Scheduler (one-off at T+ttl) =================
def schedule_cleanup(session_id: str, voice_ids, ttl_seconds: int = DEFAULT_TTL):
    # buffer avoids "in the past" validation from slight clock skew
    buffer_sec = 90
    fire_dt = dt.datetime.utcnow() + dt.timedelta(seconds=ttl_seconds + buffer_sec)
    when = fire_dt.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%S")  # no 'Z'

    name = f"session-{session_id}"
    payload = json.dumps(
        {
            "session_id": session_id,
            "voice_ids": voice_ids,
            "due_epoch": int(fire_dt.timestamp()),
        }
    )

    body = {
        "GroupName": SCHEDULER_GROUP,
        "Name": name,
        "State": "ENABLED",
        "FlexibleTimeWindow": {"Mode": "OFF"},
        "ScheduleExpression": f"at({when})",
        "ScheduleExpressionTimezone": "UTC",
        "ActionAfterCompletion": "DELETE",  # auto-clean schedule after it fires
        "Target": {
            "Arn": CLEANUP_LAMBDA_ARN,
            "RoleArn": SCHEDULER_ROLE_ARN,
            "Input": payload,
            "RetryPolicy": {
                "MaximumEventAgeInSeconds": 60,
                "MaximumRetryAttempts": 2,
            },
        },
    }

    try:
        sch.update_schedule(**body)
        return {"action": "updated", "fires_at": when}
    except sch.exceptions.ResourceNotFoundException:
        sch.create_schedule(**body)
        return {"action": "created", "fires_at": when}


# ================= State defaults =================
DEFAULTS = {
    "session_started": False,
    "chat_log": [],
    "audio_key": None,
    "who": "",
    "rs": "",
    "lang": "ar",
    "voice_id": None,
    "start_chat_disabled": False,
    "audio_file_id": None,
    "session_id": None,
    "expires_at": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ================= Restore from leases on refresh =================
if SID and not st.session_state.get("session_started"):
    # Try restoring from DDB lease
    lease = get_lease(SID)
    if lease:
        st.session_state.session_id = SID
        st.session_state.who = lease.get("who", "")
        st.session_state.rs = lease.get("rs", "")
        st.session_state.lang = lease.get("lang", "ar")
        st.session_state.voice_id = lease.get("el_voice_id")
        st.session_state.audio_key = lease.get("audio_key")
        st.session_state.chat_log = lease.get("chat_log", [])
        st.session_state.expires_at = int(lease.get("expires_at_epoch", 0)) or None
        st.session_state.session_started = (
            lease.get("status", "") == "active"
            and st.session_state.expires_at
            and time.time() < st.session_state.expires_at
        )

# ================= Sidebar (start session) =================
with st.sidebar:
    st.markdown("### Upload voice sample to start")
    audio_file = st.file_uploader("Upload .wav file", type=["wav"])

    if audio_file is not None and audio_file != st.session_state.get("audio_file_id"):
        st.session_state.start_chat_disabled = False
        st.session_state.audio_file_id = audio_file

    who = st.text_input("Who are you?", value=st.session_state.who)
    rs = st.text_input("Talking to (relation)", value=st.session_state.rs)
    lang = st.selectbox("Language", ["ar", "en", "fr"], index=0)
    first_message = st.text_area("First prompt", value="Hello, how are you?")

    start_disabled = st.session_state.start_chat_disabled or (audio_file is None)

    if st.button("Start Chat", disabled=start_disabled):
        # Init a brand-new session
        session_id = str(uuid.uuid4())
        st.session_state.session_id = session_id
        set_sid_in_url(session_id)  # put sid in URL so refresh can restore

        st.session_state.start_chat_disabled = True
        st.session_state.chat_log = []
        st.session_state.who = who
        st.session_state.rs = rs
        st.session_state.lang = lang

        unique_key = f"{uuid.uuid4()}.wav"
        s3.upload_fileobj(audio_file, S3_BUCKET, unique_key)
        st.session_state.audio_key = unique_key

        payload = {
            "who": who,
            "rs": rs,
            "text": first_message,
            "lang": lang,
            "voice_id": None,
            "bucket": S3_BUCKET,
            "key": unique_key,
        }

        with st.spinner("Starting chat..."):
            r = requests.post(
                LAMBDA_TTS, data={"data": json.dumps(payload)}, timeout=60
            )

        if r.ok:
            result = r.json()
            st.session_state.voice_id = result.get("voice_id")
            audio_key = result.get("audio_key")
            st.session_state.chat_log.append(
                {"user": first_message, "bot": f"s3_key:{audio_key}"}
            )

            now = int(time.time())
            exp = now + DEFAULT_TTL
            st.session_state.expires_at = exp
            st.session_state.session_started = True

            # Write lease row (DDB) and schedule cleanup
            put_lease_item(
                session_id=session_id,
                voice_id=st.session_state.voice_id,
                who=who,
                rs=rs,
                lang=lang,
                audio_key=st.session_state.audio_key,
                chat_log=st.session_state.chat_log,
                started_at=now,
                expires_at=exp,
                status="active",
            )

            try:
                schedule_cleanup(
                    session_id=session_id,
                    voice_ids=(
                        [st.session_state.voice_id] if st.session_state.voice_id else []
                    ),
                    ttl_seconds=DEFAULT_TTL,
                )
                st.toast("Cleanup scheduled in 10 minutes.", icon="⏱️")
            except Exception as e:
                st.warning(f"Could not schedule cleanup: {e}")
        else:
            st.error(f"❌ Failed to start chat (HTTP {r.status_code})")
            try:
                st.code(r.text[:2000])
            except Exception:
                pass

# ================= Main chat =================
if st.session_state.session_started:
    left = seconds_left()

    # ---------- Live countdown + block UI at 0 ----------
    if st.session_state.expires_at:
        html(
            f"""
    <div id="mbx-countdown" 
        style="font-size:0.95rem;
                opacity:0.95;
                margin:6px 0;
                color:white;   /* force white text */
                font-weight:500;">
    </div>
    <script>
    const expiry = {int(st.session_state.expires_at)} * 1000;
    const label  = document.getElementById('mbx-countdown');
    function pad(n) {{ return String(n).padStart(2,'0'); }}

    function tick() {{
        const left = Math.max(0, Math.floor((expiry - Date.now())/1000));
        const m = Math.floor(left/60), s = left % 60;
        label.textContent = "⏱️ Session ends in " + pad(m) + ":" + pad(s);

        if (left <= 0) {{
        label.textContent = "🛑 Session ended";
        label.style.color = "red";  // make it red when expired
        const inputs = document.querySelectorAll('input, textarea, button');
        inputs.forEach(el => {{ try {{ el.disabled = true; }} catch (e) {{}} }});
        return;
        }}
        setTimeout(tick, 1000);
    }}
    tick();
    </script>
    """,
            height=36,
        )

    # Server-side guard: flip state + mark lease ended
    left = seconds_left()
    if left == 0:
        end_session_local("time limit reached")

    st.markdown(f"### Chat with: `{st.session_state.who}`")

    for entry in st.session_state.chat_log:
        with st.chat_message("user"):
            st.markdown(entry["user"])
        with st.chat_message("assistant"):
            if entry["bot"].startswith("s3_key:"):
                key = entry["bot"].split("s3_key:")[1]
                st.audio(fetch_audio_bytes(key), format="audio/wav")
            else:
                st.markdown(entry["bot"])

    user_input = st.chat_input("Type your message...", disabled=(seconds_left() == 0))

    if user_input and seconds_left() != 0:
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                payload = {
                    "who": st.session_state.who,
                    "rs": st.session_state.rs,
                    "text": user_input,
                    "lang": st.session_state.lang,
                    "voice_id": st.session_state.voice_id,
                    "bucket": S3_BUCKET,
                    "key": st.session_state.audio_key,
                }
                r = requests.post(
                    LAMBDA_TTS, data={"data": json.dumps(payload)}, timeout=60
                )

                if r.ok:
                    result = r.json()
                    st.session_state.voice_id = result.get("voice_id")
                    audio_key = result.get("audio_key")
                    st.session_state.chat_log.append(
                        {"user": user_input, "bot": f"s3_key:{audio_key}"}
                    )
                    st.audio(fetch_audio_bytes(audio_key), format="audio/wav")

                    # Persist incremental changes to the lease
                    update_lease_fields(
                        st.session_state.session_id,
                        {
                            "el_voice_id": st.session_state.voice_id,
                            "chat_log": st.session_state.chat_log,
                        },
                    )
                else:
                    st.error(f"❌ Chat failed (HTTP {r.status_code})")
                    try:
                        st.code(r.text[:2000])
                    except Exception:
                        pass
