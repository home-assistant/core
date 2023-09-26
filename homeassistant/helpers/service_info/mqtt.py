"""MQTT Discovery data."""
from dataclasses import dataclass
import datetime as dt

from homeassistant.data_entry_flow import BaseServiceInfo

ReceivePayloadType = str | bytes


@dataclass(slots=True)
class MqttServiceInfo(BaseServiceInfo):
    """Prepared info from mqtt entries."""

    topic: str
    payload: ReceivePayloadType
    qos: int
    retain: bool
    subscribed_topic: str
    timestamp: dt.datetime
