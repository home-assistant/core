"""Registry-free JSON codec for channel-core tests."""

import json
from typing import Any

from homeassistant_sandbox.channel import Frame, FrameKind


class JsonCodec:
    """One-JSON-object-per-frame codec for channel-core tests."""

    def encode(self, frame: Frame) -> bytes:
        """Encode a frame to a compact JSON object."""
        message: dict[str, Any]
        if frame.kind is FrameKind.CALL:
            message = {"id": frame.id, "type": frame.type, "payload": frame.payload}
        elif frame.kind is FrameKind.PUSH:
            message = {"type": frame.type, "payload": frame.payload}
        elif frame.ok:
            message = {"id": frame.id, "ok": True, "result": frame.result}
        else:
            message = {
                "id": frame.id,
                "ok": False,
                "error": frame.error,
                "error_type": frame.error_type,
            }
            if frame.error_data is not None:
                message["error_data"] = frame.error_data
        return json.dumps(message, separators=(",", ":")).encode("utf-8")

    def decode(self, data: bytes) -> Frame:
        """Decode a JSON object into a frame, inferring the kind from keys."""
        message = json.loads(data)
        has_id = "id" in message
        has_type = "type" in message
        if has_id and not has_type:
            # Response to a call we sent out.
            if message.get("ok"):
                return Frame.ok_response(message["id"], message.get("result"))
            return Frame.error_response(
                message["id"],
                message.get("error", "unknown error"),
                message.get("error_type"),
                message.get("error_data"),
            )
        if not has_id:
            return Frame.push(message.get("type", ""), message.get("payload"))
        return Frame.call(message["id"], message["type"], message.get("payload"))
