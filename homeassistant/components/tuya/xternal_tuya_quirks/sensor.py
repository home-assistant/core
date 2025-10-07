"""Common cover quirks for Tuya devices."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .homeassistant import TuyaEntityCategory, TuyaSensorDeviceClass


class CommonSensorType(StrEnum):
    """Common sensor types."""

    TIME_TOTAL = "time_total"


@dataclass(kw_only=True)
class TuyaSensorDefinition:
    """Definition for a sensor entity."""

    key: str

    sensor_type: CommonSensorType

    dp_code: str


# The following needs to be kept synchronised with Home Assistant


@dataclass(kw_only=True)
class SensorHADefinition:
    """Definition for a Tuya sensor."""

    device_class: TuyaSensorDeviceClass | None = None
    entity_category: TuyaEntityCategory | None = None
    state_translations: dict[str, str] | None = None
    translation_key: str
    translation_string: str


COMMON_SENSOR_DEFINITIONS: dict[CommonSensorType, SensorHADefinition] = {
    CommonSensorType.TIME_TOTAL: SensorHADefinition(
        translation_key="last_operation_duration",
        translation_string="Last operation duration",
        entity_category=TuyaEntityCategory.DIAGNOSTIC,
    )
}
