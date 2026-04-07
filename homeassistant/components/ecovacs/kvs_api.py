"""KVS camera API calls for the Ecovacs integration.

Handles HTTP session management (start_watch/v2, end_watch, verify_video_pwd)
and MQTT P2P commands (videoOpened, setAudioCallState) required to establish
and maintain a KVS WebRTC camera session with the robot.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import random
import string
import time
from typing import Any
import uuid

from aiohttp import ClientSession, ClientTimeout

_LOGGER = logging.getLogger(__name__)

# API gateway for KVS session control.
# Different from the portal URL used by deebot-client for GetDeviceList.
# The datacenter segment (eu / na / ww) must match the user's continent.
_MA_GW_TEMPLATE = "https://api-app.dc-{continent}.ww.ecouser.net"


def get_ma_gw(continent: str) -> str:
    """Return the KVS API gateway URL for the given continent (eu / na / ww)."""
    return _MA_GW_TEMPLATE.format(continent=continent)


# App metadata embedded in API request headers and query params.
_APP_VERSION = "2.1.0"
_APP_VERSION_HEADER = "3.12.0"
_APP_PLATFORM = "android"
_APP_PLATFORM_PARAMS = "Android"
_APP_LANG = "en"

# PIN encoding: MD5("eco_" + pin_digits)
PIN_PREFIX = "eco_"

_TRACK_ID_CHARS = string.ascii_letters + string.digits


def encode_pin(pin_digits: str) -> str:
    """Encode the camera PIN as MD5(PIN_PREFIX + pin_digits)."""
    return hashlib.md5((PIN_PREFIX + pin_digits).encode()).hexdigest()


def generate_video_track_id() -> str:
    """Generate a random 10-character alphanumeric video track ID."""
    return "".join(random.choices(_TRACK_ID_CHARS, k=10))


def _sign(ts_ms: str) -> str:
    """Compute request signature as SHA1(shared_secret + timestamp_ms)."""
    return hashlib.sha1(
        ("ecovacs2ea31cf06e6711eaa0aff7b9558a534e" + ts_ms).encode()
    ).hexdigest()


def _make_headers(token: str, user_id: str, country: str) -> dict[str, str]:
    """Build standard HTTP request headers for Ecovacs API calls."""
    ts = str(int(time.time() * 1000))
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "appid": "ecovacs",
        "plat": _APP_PLATFORM,
        "ts": ts,
        "country": country,
        "lang": _APP_LANG,
        "ucid": "",
        "v": _APP_VERSION_HEADER,
        "sign": _sign(ts),
        "token": token,
        "Authorization": f"Bearer {token}",
        "userid": user_id,
    }


async def verify_video_pwd(
    session: ClientSession,
    *,
    token: str,
    user_id: str,
    did: str,
    pin_hash: str,
    country: str,
    ma_gw: str = get_ma_gw("ww"),
) -> dict[str, Any]:
    """Verify the camera PIN before initiating a stream.

    POST /api/appsvr/video/pwd/verify
    """
    url = f"{ma_gw}/api/appsvr/video/pwd/verify"
    body = json.dumps({"did": did, "pwd": pin_hash})
    async with session.post(
        url,
        data=body,
        headers=_make_headers(token, user_id, country),
        timeout=ClientTimeout(total=10),
    ) as resp:
        raw = await resp.text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}
    _LOGGER.debug("verify_video_pwd ret=%s code=%s", data.get("ret"), data.get("code"))
    return data


async def start_watch_v2(
    session: ClientSession,
    *,
    token: str,
    user_id: str,
    did: str,
    mid: str,
    res: str,
    pin_hash: str,
    video_track_id: str | None = None,
    country: str,
    ma_gw: str = get_ma_gw("ww"),
) -> dict[str, Any]:
    """Initiate a KVS video session for the robot.

    GET /api/appsvr/akvs/start_watch/v2
    Returns AWS credentials, region, channel, client_id, and session ID.
    """
    if video_track_id is None:
        video_track_id = generate_video_track_id()

    params = {
        "videoTrackId": video_track_id,
        "lang": _APP_LANG,
        "plat": _APP_PLATFORM_PARAMS,
        "av": _APP_VERSION,
        "did": did,
        "mid": mid,
        "res": res,
        "pwd": pin_hash,
    }

    async with session.get(
        f"{ma_gw}/api/appsvr/akvs/start_watch/v2",
        params=params,
        headers=_make_headers(token, user_id, country),
        timeout=ClientTimeout(total=20),
    ) as resp:
        raw = await resp.text()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}
        _LOGGER.debug(
            "start_watch_v2 ret=%s session=%s", data.get("ret"), data.get("session")
        )
    return data


async def end_watch(
    session: ClientSession,
    *,
    token: str,
    user_id: str,
    session_id: str,
    video_track_id: str,
    country: str,
    ma_gw: str = get_ma_gw("ww"),
) -> None:
    """Terminate the video session server-side.

    GET /api/appsvr/akvs/end_watch
    """
    params = {
        "videoTrackId": video_track_id,
        "lang": _APP_LANG,
        "plat": _APP_PLATFORM_PARAMS,
        "av": _APP_VERSION,
        "sid": session_id,
    }
    try:
        async with session.get(
            f"{ma_gw}/api/appsvr/akvs/end_watch",
            params=params,
            headers=_make_headers(token, user_id, country),
            timeout=ClientTimeout(total=10),
        ) as resp:
            _LOGGER.debug("end_watch HTTP %d", resp.status)
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("end_watch failed: %s", err)


async def send_video_opened(
    *,
    enqueue_publish: Any,
    token: str,
    user_id: str,
    user_resource: str,
    did: str,
    mid: str,
    res: str,
) -> None:
    """Notify the robot that the viewer is ready to receive video via MQTT."""
    await _send_p2p_mqtt_cmd(
        enqueue_publish=enqueue_publish,
        token=token,
        user_id=user_id,
        user_resource=user_resource,
        did=did,
        mid=mid,
        res=res,
        cmd_name="videoOpened",
        cmd_data=None,
    )


async def set_audio_call_state(
    *,
    enqueue_publish: Any,
    token: str,
    user_id: str,
    user_resource: str,
    did: str,
    mid: str,
    res: str,
    client_id: str,
    state: int,
) -> None:
    """Send setAudioCallState to the robot via MQTT (state: 1=start, 0=stop)."""
    await _send_p2p_mqtt_cmd(
        enqueue_publish=enqueue_publish,
        token=token,
        user_id=user_id,
        user_resource=user_resource,
        did=did,
        mid=mid,
        res=res,
        cmd_name="setAudioCallState",
        cmd_data={"clientId": client_id, "state": state},
    )


async def _send_p2p_mqtt_cmd(
    *,
    enqueue_publish: Any,
    token: str,
    user_id: str,
    user_resource: str,
    did: str,
    mid: str,
    res: str,
    cmd_name: str,
    cmd_data: dict[str, Any] | None,
) -> None:
    """Publish a P2P MQTT command to the robot via the KVS MQTT session."""
    req_id = uuid.uuid4().hex[:8]
    ts = str(int(time.time() * 1000))
    tz_offset = int(
        _dt.datetime.now(_dt.UTC).astimezone().utcoffset().total_seconds() / 60
    )

    payload = json.dumps(
        {
            "header": {"pri": 2, "ts": ts, "tzm": tz_offset, "ver": "0.0.22"},
            "body": {"data": cmd_data},
        }
    )
    topic = (
        f"iot/p2p/{cmd_name}/{user_id}/ecouser/{user_resource}"
        f"/{did}/{mid}/{res}/q/{req_id}/j"
    )
    _LOGGER.debug("MQTT P2P %s topic=%s", cmd_name, topic)
    await enqueue_publish(topic, payload.encode(), qos=0)
