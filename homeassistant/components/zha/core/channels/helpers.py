"""Helpers for use with ZHA Zigbee channels."""
from .base import ZigbeeChannel


def is_hue_motion_sensor(channel: ZigbeeChannel) -> bool:
    """Return true if the manufacturer and model match known Hue motion sensor models."""
    return channel.cluster.endpoint.manufacturer in (
        "Philips",
        "Signify Netherlands B.V.",
    ) and channel.cluster.endpoint.model in (
        "SML001",
        "SML002",
        "SML003",
        "SML004",
    )
