"""Support for Genius Hub sensor devices."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from . import DOMAIN, GeniusDevice, GeniusEntity

GH_STATE_ATTR = "batteryLevel"

GH_LEVEL_MAPPING = {
    "error": "Errors",
    "warning": "Warnings",
    "information": "Information",
}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    broker = hass.data[DOMAIN]["broker"]

    entities: list[GeniusBattery | GeniusIssue] = [
        GeniusBattery(broker, d, GH_STATE_ATTR)
        for d in broker.client.device_objs
        if GH_STATE_ATTR in d.data["state"]
    ]
    entities.extend([GeniusIssue(broker, i) for i in list(GH_LEVEL_MAPPING)])

    async_add_entities(entities, update_before_add=True)


class GeniusBattery(GeniusDevice, SensorEntity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, broker, device, state_attr) -> None:
        """Initialize the sensor."""
        super().__init__(broker, device)

        self._state_attr = state_attr

        self._attr_name = f"{device.type} {device.id}"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        if "_state" in self._device.data:  # only for v3 API
            interval = timedelta(
                seconds=self._device.data["_state"].get("wakeupInterval", 30 * 60)
            )
            if (
                not self._last_comms
                or self._last_comms < dt_util.utcnow() - interval * 3
            ):
                return "mdi:battery-unknown"

        battery_level = self._device.data["state"][self._state_attr]
        if battery_level == 255:
            return "mdi:battery-unknown"
        if battery_level < 40:
            return "mdi:battery-alert"

        icon = "mdi:battery"
        if battery_level <= 95:
            icon += f"-{int(round(battery_level / 10 - 0.01)) * 10}"

        return icon

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return SensorDeviceClass.BATTERY

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement of the sensor."""
        return PERCENTAGE

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        level = self._device.data["state"][self._state_attr]
        return level if level != 255 else 0


class GeniusIssue(GeniusEntity, SensorEntity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, broker, level) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._hub = broker.client
        self._unique_id = f"{broker.hub_uid}_{GH_LEVEL_MAPPING[level]}"

        self._attr_name = f"GeniusHub {GH_LEVEL_MAPPING[level]}"
        self._level = level
        self._issues: list = []

    @property
    def native_value(self) -> int:
        """Return the number of issues."""
        return len(self._issues)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {f"{self._level}_list": self._issues}

    async def async_update(self) -> None:
        """Process the sensor's state data."""
        self._issues = [
            i["description"] for i in self._hub.issues if i["level"] == self._level
        ]
