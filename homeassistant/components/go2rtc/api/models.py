"""Go2rtc Python models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from mashumaro.mixins.orjson import DataClassORJSONMixin


@dataclass
class Streams(DataClassORJSONMixin):
    """Streams model."""

    streams: dict[str, Stream]


@dataclass
class Stream:
    """Stream model."""

    producers: list[Producer]


@dataclass
class Producer:
    """Producer model."""

    url: str


@dataclass
class WebRTCSdp(DataClassORJSONMixin):
    """WebRTC SDP model."""

    type: Literal["offer", "answer"]
    sdp: str


@dataclass
class WebRTCSdpOffer(WebRTCSdp):
    """WebRTC SDP offer model."""

    type: Literal["offer"] = field(default="offer", init=False)


@dataclass
class WebRTCSdpAnswer(WebRTCSdp):
    """WebRTC SDP answer model."""

    type: Literal["answer"] = field(default="answer", init=False)
