"""Support for MQTT message handling.

This module much remain lightweight as core imports
it for discovery.
"""

from dataclasses import dataclass
import datetime as dt

from homeassistant.data_entry_flow import BaseServiceInfo

from .models import ReceivePayloadType


@dataclass
class MqttServiceInfo(BaseServiceInfo):
    """Prepared info from mqtt entries."""

    topic: str
    payload: ReceivePayloadType
    qos: int
    retain: bool
    subscribed_topic: str
    timestamp: dt.datetime
