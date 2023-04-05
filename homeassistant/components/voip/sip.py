"""Implementation of SIP (Session Initiation Protocol)."""
import asyncio
from dataclasses import dataclass
import logging
import re

from homeassistant.const import __version__
from homeassistant.core import HomeAssistant

from .error import VoipError

SIP_PORT = 5060

_LOGGER = logging.getLogger(__name__)
_CRLF = "\r\n"
_SDP_USERNAME = "homeassistant"
_SDP_ID = "".join(str(ord(c)) for c in "hass")  # 10497115115
_OPUS_PAYLOAD = "123"

# <sip:IP:PORT>;tag=...
_SIP_IP = re.compile(r"^<sip:(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):\d+>$")


@dataclass
class CallInfo:
    """Information gathered from an INVITE message."""

    caller_ip: str
    caller_sip_port: int
    caller_rtp_port: int
    server_ip: str
    headers: dict[str, str]


class SipDatagramProtocol(asyncio.DatagramProtocol):
    """UDP server for the Session Initiation Protocol (SIP)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr):
        """Handle INVITE SIP messages."""
        message = data.decode()
        method, headers, body = self._parse_sip(message)

        if method and (method.lower() != "invite"):
            # Not an INVITE message
            return

        caller_ip, caller_sip_port = addr
        _LOGGER.debug(
            "Incoming call from ip=%s, port=%s",
            caller_ip,
            caller_sip_port,
        )

        # Extract caller's RTP port from SDP.
        # See: https://datatracker.ietf.org/doc/html/rfc2327
        caller_rtp_port: int | None = None
        body_lines = body.splitlines()
        for line in body_lines:
            line = line.strip()
            if line:
                key, value = line.split("=", maxsplit=1)
                if key == "m":
                    parts = value.split()
                    if parts[0] == "audio":
                        caller_rtp_port = int(parts[1])

        if caller_rtp_port is None:
            raise VoipError("No caller RTP port")

        # Extract our visible IP from SIP header.
        # This must be the IP we use for RTP.
        server_ip_match = _SIP_IP.match(headers["to"])
        if server_ip_match is None:
            raise VoipError("Failed to find 'to' IP address")
        server_ip = server_ip_match.group(1)

        self.on_call(
            CallInfo(
                caller_ip=caller_ip,
                caller_sip_port=caller_sip_port,
                caller_rtp_port=caller_rtp_port,
                server_ip=server_ip,
                headers=headers,
            )
        )

    def on_call(self, call_info: CallInfo):
        """Callback for incoming call."""

    def answer(
        self,
        call_info: CallInfo,
        server_rtp_port: int,
    ):
        """Send OK message to caller with our IP and RTP port."""
        if self.transport is None:
            return

        # SDP = Session Description Protocol
        # See: https://datatracker.ietf.org/doc/html/rfc2327
        body_lines = [
            "v=0",
            f"o={_SDP_USERNAME} {_SDP_ID} 1 IN IP4 {call_info.server_ip}",
            f"s={_SDP_USERNAME} {__version__}",
            f"c=IN IP4 {call_info.server_ip}",
            "t=0 0",
            f"m=audio {server_rtp_port} RTP/AVP {_OPUS_PAYLOAD}",
            f"a=rtpmap:{_OPUS_PAYLOAD} opus/48000/2",
            "a=ptime:20",
            "a=maxptime:150",
            "a=sendrecv",
            _CRLF,
        ]
        body = _CRLF.join(body_lines)

        response_headers = {
            "Via": call_info.headers["via"],
            "From": call_info.headers["from"],
            "To": call_info.headers["to"],
            "Call-ID": call_info.headers["call-id"],
            "Content-Type": "application/sdp",
            "Content-Length": len(body),
            "CSeq": call_info.headers["cseq"],
            "Contact": call_info.headers["contact"],
            "User-Agent": f"{_SDP_USERNAME} 1.0",
            "Allow": "INVITE, ACK, BYE, CANCEL, OPTIONS",
        }
        response_lines = ["SIP/2.0 200 OK"]

        for key, value in response_headers.items():
            response_lines.append(f"{key}: {value}")

        response_lines.append(_CRLF)
        response_str = _CRLF.join(response_lines) + body
        response_bytes = response_str.encode()

        self.transport.sendto(
            response_bytes,
            (call_info.caller_ip, call_info.caller_sip_port),
        )
        _LOGGER.debug(
            "Sent OK to ip=%s, port=%s with rtp_port=%s",
            call_info.caller_ip,
            call_info.caller_sip_port,
            server_rtp_port,
        )

    def _parse_sip(self, message: str) -> tuple[str | None, dict[str, str], str]:
        """Parse SIP message and return method, headers, and body."""
        lines = message.splitlines()

        method: str | None = None
        headers: dict[str, str] = {}
        offset: int = 0

        # See: https://datatracker.ietf.org/doc/html/rfc3261
        for i, line in enumerate(lines):
            if line:
                offset += len(line) + len(_CRLF)

            if i == 0:
                method = line.split()[0]
            elif not line:
                break
            else:
                key, value = line.split(":", maxsplit=1)
                headers[key.lower()] = value.strip()

        body = message[offset:]

        return method, headers, body
