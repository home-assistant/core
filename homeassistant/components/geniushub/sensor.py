"""Support for Genius Hub sensor devices."""
from datetime import timedelta
from typing import Any, Awaitable, Dict

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.util.dt import utcnow

from . import DOMAIN, GeniusDevice, GeniusEntity

GH_STATE_ATTR = "batteryLevel"

GH_LEVEL_MAPPING = {
    "error": "Errors",
    "warning": "Warnings",
    "information": "Information",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    if discovery_info is None:
        return

    client = hass.data[DOMAIN]["client"]

    sensors = [
        GeniusBattery(d, GH_STATE_ATTR)
        for d in client.device_objs
        if GH_STATE_ATTR in d.data["state"]
    ]
    issues = [GeniusIssue(client, i) for i in list(GH_LEVEL_MAPPING)]

    async_add_entities(sensors + issues, update_before_add=True)


class GeniusBattery(GeniusDevice):
    """Representation of a Genius Hub sensor."""

    def __init__(self, device, state_attr) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._device = device
        self._state_attr = state_attr

        self._name = f"{device.type} {device.id}"

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        interval = timedelta(
            seconds=self._device.data["_state"].get("wakeupInterval", 30 * 60)
        )
        if self._last_comms < utcnow() - interval * 3:
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
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of the sensor."""
        return "%"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        level = self._device.data["state"][self._state_attr]
        return level if level != 255 else 0


class GeniusIssue(GeniusEntity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, hub, level) -> None:
        """Initialize the sensor."""
        super().__init__()

        self._hub = hub
        self._name = f"Genius Hub {GH_LEVEL_MAPPING[level]}"
        self._level = level
        self._issues = []

    @property
    def state(self) -> str:
        """Return the number of issues."""
        return len(self._issues)

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the device state attributes."""
        return {f"{self._level}_list": self._issues}

    async def async_update(self) -> Awaitable[None]:
        """Process the sensor's state data."""
        self._issues = [
            i["description"] for i in self._hub.issues if i["level"] == self._level
        ]
