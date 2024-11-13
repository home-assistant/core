"""Data classes for Victron Venus OS integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional

from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass


@dataclass
class TopicDescriptor:
    """Describes the topic, how to map it and how to parse it."""

    message_type: str  # 'device', 'sensor', or 'system'
    short_id: str  # short id of the attribute/value (also translation key)
    unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    precision: int | None = None
    unwrapper: Callable[[str], int | float | str] | None = None


@dataclass
class ParsedTopic:
    """Parsed topic."""

    installation_id: str
    device_id: str
    device_type: str
    phase: str
    wildcards_with_device_type: str
    wildcards_without_device_type: str

    @classmethod
    def __get_index_and_phase(cls, topic_parts: list[str]) -> tuple[int, str]:
        """Get the index of the phase and the phase itself."""
        for i, part in enumerate(topic_parts):
            if part in {"L1", "L2", "L3"}:
                return i, part
        return -1, ""

    @classmethod
    def from_topic(cls, topic: str) -> Optional["ParsedTopic"]:
        """Create a ParsedTopic from a topic and payload."""

        # example : N/123456789012/grid/30/Ac/L1/Energy/Forward
        topic_parts = topic.split("/")

        if len(topic_parts) < 4:
            return None

        wildcard_topic_parts = topic_parts.copy()

        installation_id = topic_parts[1]
        wildcard_topic_parts[1] = "+"
        device_type = topic_parts[2]
        if device_type == "platform":  # platform is not a device type
            device_type = "system"
        device_id = topic_parts[3]
        wildcard_topic_parts[3] = "+"

        phaseindex, phase = ParsedTopic.__get_index_and_phase(topic_parts)
        if phaseindex != -1:
            wildcard_topic_parts[phaseindex] = "+"

        wildcards_with_device_type = "/".join(wildcard_topic_parts)

        wildcard_topic_parts[2] = "+"

        wildcards_without_device_type = "/".join(wildcard_topic_parts)

        return cls(
            installation_id,
            device_id,
            device_type,
            phase,
            wildcards_with_device_type,
            wildcards_without_device_type,
        )
