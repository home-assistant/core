"""Helpers for use with ZHA Zigbee cluster handlers."""
from . import ClusterHandler


def is_hue_motion_sensor(cluster_handler: ClusterHandler) -> bool:
    """Return true if the manufacturer and model match known Hue motion sensor models."""
    return cluster_handler.cluster.endpoint.manufacturer in (
        "Philips",
        "Signify Netherlands B.V.",
    ) and cluster_handler.cluster.endpoint.model in (
        "SML001",
        "SML002",
        "SML003",
        "SML004",
    )
