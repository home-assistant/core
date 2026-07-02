"""Codec registry for zha_infrared payload translations."""

import logging
from collections.abc import Callable
from typing import Any

from .broadlink import (
    decode_broadlink_base64_to_raw_timings,
    encode_raw_to_broadlink_base64,
)
from .esphome import decode_raw_passthrough, encode_raw_passthrough
from .pronto import decode_pronto_hex_to_raw_timings, encode_raw_to_pronto_hex
from .tuya import decode_tuya_payload_to_raw_timings, encode_raw_to_tuya_base64

_LOGGER = logging.getLogger(__name__)

EncodeFn = Callable[[list[int], int | None], Any]
DecodeFn = Callable[[Any], list[int] | None]

CODEC_REGISTRY: dict[str, EncodeFn] = {
    "tuya_base64_rawtimings_v1": encode_raw_to_tuya_base64,
    "esphome_rawtimings_v1": encode_raw_passthrough,
    "broadlink_packet_base64_v1": encode_raw_to_broadlink_base64,
    "xiaomi_miio_pronto_hex_v1": encode_raw_to_pronto_hex,
    "pronto_hex_v1": encode_raw_to_pronto_hex,
}

DECODE_REGISTRY: dict[str, DecodeFn] = {
    "tuya_base64_rawtimings_v1": decode_tuya_payload_to_raw_timings,
    "esphome_rawtimings_v1": decode_raw_passthrough,
    "broadlink_packet_base64_v1": decode_broadlink_base64_to_raw_timings,
    "xiaomi_miio_pronto_hex_v1": decode_pronto_hex_to_raw_timings,
    "pronto_hex_v1": decode_pronto_hex_to_raw_timings,
}


def encode_payload(
    codec_name: str, timings: list[int], modulation: int | None = None
) -> Any:
    """Encode raw timings using a named codec."""
    encoder = CODEC_REGISTRY.get(codec_name)
    if encoder is None:
        raise ValueError(f"Unknown codec: {codec_name}")
    return encoder(timings, modulation)


def decode_received_payload(codec_name: str, payload: Any) -> list[int] | None:
    """Decode payload into signed raw timings when codec supports it."""
    decoder = DECODE_REGISTRY.get(codec_name)
    if decoder is None:
        return None
    try:
        timings = decoder(payload)
    except (TypeError, ValueError):
        _LOGGER.debug("Failed decoding payload with codec %s", codec_name, exc_info=True)
        return None
    if not isinstance(timings, list):
        return None
    return [int(item) for item in timings]
