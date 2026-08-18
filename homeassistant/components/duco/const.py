"""Constants for the Duco integration."""

from datetime import timedelta

from duco_connectivity.models import NodeType

from homeassistant.const import Platform

DOMAIN = "duco"
PLATFORMS = [Platform.FAN, Platform.SELECT, Platform.SENSOR]
SCAN_INTERVAL = timedelta(seconds=10)
BOX_NODE_ID = 1
VENTILATION_CAPABLE_NODE_TYPES: tuple[NodeType, ...] = (
    NodeType.BOX,
    NodeType.VLV,
    NodeType.VLVRH,
    NodeType.VLVVOC,
    NodeType.VLVCO2,
    NodeType.VLVCO2RH,
    NodeType.EAV,
    NodeType.EAVRH,
    NodeType.EAVVOC,
    NodeType.EAVCO2,
)
