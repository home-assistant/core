"""KVS WebRTC signaling utilities for the Ecovacs camera integration.

Provides AWS SigV4 URL signing and KVS WebSocket message builders
(SDP_OFFER, ICE_CANDIDATE) used during WebRTC session setup.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import hmac
import json
import logging
import urllib.parse

_LOGGER = logging.getLogger(__name__)


def _b64(s: str) -> str:
    """Encode a UTF-8 string as base64."""
    return base64.b64encode(s.encode()).decode()


def sign_wss_url(
    wss_endpoint: str,
    channel_arn: str,
    client_id: str,
    creds: dict[str, str],
    region: str,
) -> str:
    """Sign the KVS WebSocket URL using AWS Signature v4 as a VIEWER.

    Includes X-Amz-ClientId to identify this connection to the signaling channel.
    """
    host = wss_endpoint.replace("wss://", "").split("/")[0]
    now = datetime.now(UTC)
    date_str = now.strftime("%Y%m%d")
    time_str = now.strftime("%Y%m%dT%H%M%SZ")
    service = "kinesisvideo"

    qs_params: dict[str, str] = {
        "X-Amz-ChannelARN": channel_arn,
        "X-Amz-ClientId": client_id,
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": (
            f"{creds['AccessKeyId']}/{date_str}/{region}/{service}/aws4_request"
        ),
        "X-Amz-Date": time_str,
        "X-Amz-Expires": "299",
        "X-Amz-SignedHeaders": "host",
    }
    if creds.get("SessionToken"):
        qs_params["X-Amz-Security-Token"] = creds["SessionToken"]

    def _url_encode(s: str) -> str:
        return urllib.parse.quote(s, safe="")

    sorted_qs = "&".join(
        f"{_url_encode(k)}={_url_encode(v)}" for k, v in sorted(qs_params.items())
    )

    canonical_req = "\n".join(
        [
            "GET",
            "/",
            sorted_qs,
            f"host:{host}\n",
            "host",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ]
    )
    scope = f"{date_str}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            time_str,
            scope,
            hashlib.sha256(canonical_req.encode()).hexdigest(),
        ]
    )

    def _hmac_sha256(key: bytes | str, msg: str) -> bytes:
        if isinstance(key, str):
            key = key.encode()
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    signing_key = _hmac_sha256(
        _hmac_sha256(
            _hmac_sha256(
                _hmac_sha256(f"AWS4{creds['SecretAccessKey']}", date_str),
                region,
            ),
            service,
        ),
        "aws4_request",
    )
    signature = _hmac_sha256(signing_key, string_to_sign).hex()
    qs_params["X-Amz-Signature"] = signature
    final_qs = "&".join(
        f"{_url_encode(k)}={_url_encode(v)}" for k, v in sorted(qs_params.items())
    )
    return f"wss://{host}/?{final_qs}"


def make_sdp_offer_msg(sdp: str, client_id: str) -> str:
    """Build a KVS WebSocket SDP_OFFER message."""
    return json.dumps(
        {
            "action": "SDP_OFFER",
            "recipientClientId": "",
            "messagePayload": _b64(json.dumps({"type": "offer", "sdp": sdp})),
            "senderClientId": client_id,
        }
    )


def make_ice_msg(candidate: str, sdp_mid: str, sdp_mline: int, client_id: str) -> str:
    """Build a KVS WebSocket ICE_CANDIDATE message."""
    return json.dumps(
        {
            "action": "ICE_CANDIDATE",
            "recipientClientId": "",
            "messagePayload": _b64(
                json.dumps(
                    {
                        "candidate": candidate,
                        "sdpMid": sdp_mid,
                        "sdpMLineIndex": sdp_mline,
                    }
                )
            ),
            "senderClientId": client_id,
        }
    )
