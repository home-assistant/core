"""Protobuf :class:`~.channel.Codec` — the production wire.

Serialises a :class:`~.channel.Frame` to the protobuf ``Frame`` envelope and
back. The envelope carries ``type`` on responses too, so this stateless codec
can look up the result message class from ``frame.type`` on both encode and
decode — the dispatch core never has to know about proto types (the registry
lives here, not on :meth:`Channel.register`).

Mirrored verbatim across the no-cross-import boundary (the same file lives at
``hass_client.codec_protobuf``); the relative imports resolve to each side's
own :mod:`messages` + ``_proto`` gencode.
"""

from typing import Any

from google.protobuf.message import Message

from ._proto import sandbox_pb2 as pb
from .channel import Frame, FrameKind
from .messages import REGISTRY

Registry = dict[str, tuple[type[Message], type[Message] | None]]


class ProtobufCodec:
    """Encode/decode :class:`Frame` objects as protobuf ``Frame`` envelopes."""

    def __init__(self, registry: Registry | None = None) -> None:
        """Build the codec over a ``type → (request_cls, result_cls)`` map."""
        self._registry = registry if registry is not None else REGISTRY

    def _classes(
        self, msg_type: str
    ) -> tuple[type[Message] | None, type[Message] | None]:
        return self._registry.get(msg_type, (None, None))

    def encode(self, frame: Frame) -> bytes:
        """Serialise a frame to the protobuf ``Frame`` envelope bytes."""
        envelope = pb.Frame(id=frame.id, type=frame.type)
        if frame.kind is FrameKind.RESPONSE:
            response = envelope.response
            response.ok = frame.ok
            if frame.ok:
                _, result_cls = self._classes(frame.type)
                response.result = _serialize_body(frame.result, result_cls)
            else:
                _fill_error(response.error, frame)
        else:
            request_cls, _ = self._classes(frame.type)
            envelope.request = _serialize_body(frame.payload, request_cls)
        return envelope.SerializeToString()

    def decode(self, data: bytes) -> Frame:
        """Rebuild a frame from protobuf ``Frame`` envelope bytes."""
        envelope = pb.Frame.FromString(data)
        msg_type = envelope.type
        body = envelope.WhichOneof("body")
        if body == "response":
            response = envelope.response
            if response.ok:
                _, result_cls = self._classes(msg_type)
                result = _parse_body(response.result, result_cls)
                return Frame.ok_response(envelope.id, result, msg_type)
            error, error_type, error_data = _read_error(response.error)
            return Frame.error_response(
                envelope.id, error, error_type, error_data, msg_type
            )
        request_cls, _ = self._classes(msg_type)
        payload = _parse_body(envelope.request, request_cls)
        if envelope.id == 0:
            return Frame.push(msg_type, payload)
        return Frame.call(envelope.id, msg_type, payload)


def _serialize_body(body: Any, cls: type[Message] | None) -> bytes:
    """Serialise a proto-message body; ``None`` becomes an empty message."""
    if body is None:
        return cls().SerializeToString() if cls is not None else b""
    if isinstance(body, Message):
        return body.SerializeToString()
    raise TypeError(
        f"ProtobufCodec expected a proto message body, got {type(body).__name__}"
    )


def _parse_body(raw: bytes, cls: type[Message] | None) -> Any:
    """Deserialise a body into ``cls``; an unregistered type decodes to None."""
    if cls is None:
        return None
    return cls.FromString(raw)


def _fill_error(error: pb.Error, frame: Frame) -> None:
    """Populate the proto ``Error`` from a failure frame.

    Carries fidelity #7's structured voluptuous data: the ``multiple`` flag
    distinguishes a ``MultipleInvalid`` from a single ``Invalid`` so the peer
    rebuilds the right exception.
    """
    error.message = frame.error or ""
    error.type = frame.error_type or ""
    data = frame.error_data
    if not data:
        return
    if data.get("kind") == "multiple":
        error.multiple = True
        for child in data.get("errors", []):
            error.invalid.add(message=child.get("msg", ""), path=child.get("path", []))
    elif data.get("kind") == "invalid":
        error.invalid.add(message=data.get("msg", ""), path=data.get("path", []))


def _read_error(error: pb.Error) -> tuple[str, str | None, dict[str, Any] | None]:
    """Rebuild ``(message, type, error_data)`` from the proto ``Error``."""
    error_data: dict[str, Any] | None = None
    if error.multiple:
        error_data = {
            "kind": "multiple",
            "errors": [
                {"kind": "invalid", "msg": item.message, "path": list(item.path)}
                for item in error.invalid
            ],
        }
    elif len(error.invalid) == 1:
        item = error.invalid[0]
        error_data = {
            "kind": "invalid",
            "msg": item.message,
            "path": list(item.path),
        }
    return error.message, (error.type or None), error_data


__all__ = ["ProtobufCodec"]
