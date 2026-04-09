"""AWS Kinesis Video Streams WebRTC signaling client."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import aiohttp
from homeassistant.components.camera import WebRTCCandidate
from webrtc_models import RTCIceCandidateInit

from .const import LOGGER


class KvsSignalingClient:
    """KVS WebRTC signaling client for SDP exchange via AWS API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        region: str,
        channel_arn: str,
        credentials: dict[str, str],
    ) -> None:
        self._session = session
        self._region = region
        self._channel_arn = channel_arn
        self._access_key = credentials["AccessKeyId"]
        self._secret_key = credentials["SecretAccessKey"]
        self._session_token = credentials.get("SessionToken", "")
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task | None = None

    async def async_get_answer_sdp(
        self, offer_sdp: str, send_message: Any,
    ) -> str | None:
        """Get answer SDP via KVS signaling, forwarding ICE candidates."""
        endpoints = await self._async_get_signaling_endpoints()
        if not endpoints:
            return None
        wss_endpoint = endpoints.get("WSS")
        if not wss_endpoint:
            LOGGER.error("KVS: No WSS endpoint found")
            return None

        signed_url = self._build_signed_wss_url(wss_endpoint)
        LOGGER.debug("KVS: Connecting to signaling channel")
        try:
            self._ws = await self._session.ws_connect(signed_url)
        except Exception as err:  # noqa: BLE001
            LOGGER.error("KVS: Signaling connection failed: %s", err)
            return None

        # Send SDP offer
        offer_msg = json.dumps({
            "action": "SDP_OFFER",
            "messagePayload": base64.b64encode(
                json.dumps({"type": "offer", "sdp": offer_sdp}).encode()
            ).decode(),
        })
        await self._ws.send_str(offer_msg)
        LOGGER.debug("KVS: SDP offer sent")

        # Wait for SDP answer, forward ICE candidates
        answer_sdp = None
        try:
            async for msg in self._ws:
                if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                    raw = msg.data if isinstance(msg.data, str) else msg.data.decode() if msg.data else None
                    if not raw:
                        continue
                    LOGGER.debug("KVS: Message received: %s", raw[:200])
                    data = json.loads(raw)
                    msg_type = data.get("messageType")
                    if msg_type == "SDP_ANSWER":
                        payload = json.loads(base64.b64decode(data["messagePayload"]).decode())
                        answer_sdp = payload.get("sdp")
                        LOGGER.debug("KVS: SDP answer received")
                        self._listen_task = asyncio.get_event_loop().create_task(
                            self._async_listen_ice(send_message)
                        )
                        return answer_sdp
                    elif msg_type == "ICE_CANDIDATE":
                        self._forward_ice_candidate(data, send_message)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break
        except Exception as err:  # noqa: BLE001
            LOGGER.error("KVS: SDP exchange failed: %s", err)
        return answer_sdp

    async def _async_listen_ice(self, send_message: Any) -> None:
        """Listen and forward ICE candidates in background."""
        try:
            async for msg in self._ws:
                if msg.type in (aiohttp.WSMsgType.TEXT, aiohttp.WSMsgType.BINARY):
                    raw = msg.data if isinstance(msg.data, str) else msg.data.decode() if msg.data else None
                    if not raw:
                        continue
                    data = json.loads(raw)
                    if data.get("messageType") == "ICE_CANDIDATE":
                        self._forward_ice_candidate(data, send_message)
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break
        except asyncio.CancelledError:
            pass
        except Exception:  # noqa: BLE001
            LOGGER.debug("KVS: ICE listener ended")

    def _forward_ice_candidate(self, data: dict, send_message: Any) -> None:
        """Parse and forward ICE candidate to frontend."""
        try:
            payload = json.loads(base64.b64decode(data["messagePayload"]).decode())
            send_message(WebRTCCandidate(
                candidate=RTCIceCandidateInit(
                    candidate=payload.get("candidate", ""),
                    sdp_mid=payload.get("sdpMid", ""),
                    sdp_m_line_index=payload.get("sdpMLineIndex", 0),
                )
            ))
        except Exception:  # noqa: BLE001
            LOGGER.debug("KVS: Failed to forward ICE candidate")

    async def async_send_ice_candidate(
        self, candidate: str, sdp_mid: str | None, sdp_mline_index: int | None
    ) -> None:
        """Send ICE candidate to master via signaling channel."""
        if not self._ws or self._ws.closed:
            return
        payload = json.dumps({
            "candidate": candidate,
            "sdpMid": sdp_mid or "0",
            "sdpMLineIndex": sdp_mline_index or 0,
        })
        msg = json.dumps({
            "action": "ICE_CANDIDATE",
            "messagePayload": base64.b64encode(payload.encode()).decode(),
        })
        await self._ws.send_str(msg)

    async def async_close(self) -> None:
        """Close signaling connection."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
        self._listen_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _async_get_signaling_endpoints(self) -> dict[str, str]:
        """Get KVS signaling channel endpoints."""
        url = f"https://kinesisvideo.{self._region}.amazonaws.com/getSignalingChannelEndpoint"
        body = json.dumps({
            "ChannelARN": self._channel_arn,
            "SingleMasterChannelEndpointConfiguration": {
                "Protocols": ["WSS", "HTTPS"], "Role": "VIEWER",
            },
        }, separators=(",", ":"))
        headers = self._sign_request("POST", url, body)
        try:
            resp = await self._session.post(url, data=body, headers=headers)
            data = await resp.json()
            endpoints = {}
            for ep in data.get("ResourceEndpointList", []):
                endpoints[ep["Protocol"]] = ep["ResourceEndpoint"]
            return endpoints
        except Exception as err:  # noqa: BLE001
            LOGGER.error("KVS: Failed to get signaling endpoints: %s", err)
            return {}

    async def async_get_ice_server_config(self) -> list[dict[str, Any]]:
        """Get KVS ICE server config (TURN/STUN)."""
        endpoints = await self._async_get_signaling_endpoints()
        https_endpoint = endpoints.get("HTTPS")
        if https_endpoint:
            return await self._async_get_ice_servers(https_endpoint)
        return []

    async def _async_get_ice_servers(self, https_endpoint: str) -> list[dict[str, Any]]:
        url = f"{https_endpoint}/v1/get-ice-server-config"
        body = json.dumps({"ChannelARN": self._channel_arn}, separators=(",", ":"))
        headers = self._sign_request("POST", url, body)
        try:
            resp = await self._session.post(url, data=body, headers=headers)
            data = await resp.json()
            return data.get("IceServerList", [])
        except Exception as err:  # noqa: BLE001
            LOGGER.error("KVS: Failed to get ICE servers: %s", err)
            return []

    def _sign_request(self, method: str, url: str, body: str) -> dict[str, str]:
        """AWS SigV4 sign HTTP request."""
        now = datetime.now(timezone.utc)
        datestamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        parsed = urlparse(url)
        host = parsed.hostname
        path = parsed.path or "/"
        service = "kinesisvideo"
        credential_scope = f"{datestamp}/{self._region}/{service}/aws4_request"
        headers_to_sign = {"host": host, "x-amz-date": amz_date}
        if self._session_token:
            headers_to_sign["x-amz-security-token"] = self._session_token
        signed_headers = ";".join(sorted(headers_to_sign.keys()))
        canonical_headers = "".join(f"{k}:{v}\n" for k, v in sorted(headers_to_sign.items()))
        payload_hash = hashlib.sha256(body.encode()).hexdigest()
        canonical_request = f"{method}\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
        string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        signing_key = self._get_signature_key(datestamp, service)
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        auth_header = f"AWS4-HMAC-SHA256 Credential={self._access_key}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
        result = {"Authorization": auth_header, "x-amz-date": amz_date, "Content-Type": "application/json"}
        if self._session_token:
            result["x-amz-security-token"] = self._session_token
        return result

    def _build_signed_wss_url(self, wss_endpoint: str) -> str:
        """Build SigV4 signed WSS URL."""
        now = datetime.now(timezone.utc)
        datestamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        parsed = urlparse(wss_endpoint)
        host = parsed.hostname
        path = parsed.path or "/"
        service = "kinesisvideo"
        credential_scope = f"{datestamp}/{self._region}/{service}/aws4_request"
        query_params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-ChannelARN": self._channel_arn,
            "X-Amz-ClientId": "ha-viewer",
            "X-Amz-Credential": f"{self._access_key}/{credential_scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": "300",
            "X-Amz-SignedHeaders": "host",
        }
        if self._session_token:
            query_params["X-Amz-Security-Token"] = self._session_token
        canonical_querystring = "&".join(
            f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in sorted(query_params.items())
        )
        canonical_request = f"GET\n{path}\n{canonical_querystring}\nhost:{host}\n\nhost\ne3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        string_to_sign = f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        signing_key = self._get_signature_key(datestamp, service)
        signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
        return f"{wss_endpoint}?{canonical_querystring}&X-Amz-Signature={signature}"

    def _get_signature_key(self, datestamp: str, service: str) -> bytes:
        """Generate AWS SigV4 signing key."""
        k_date = hmac.new(f"AWS4{self._secret_key}".encode(), datestamp.encode(), hashlib.sha256).digest()
        k_region = hmac.new(k_date, self._region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode(), hashlib.sha256).digest()
        return hmac.new(k_service, b"aws4_request", hashlib.sha256).digest()
