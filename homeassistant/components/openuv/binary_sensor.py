"""Support for OpenUV binary sensors."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.util.dt import as_local, parse_datetime, utcnow

from . import OpenUvEntity
from .const import (
    DATA_CLIENT,
    DATA_PROTECTION_WINDOW,
    DOMAIN,
    LOGGER,
    TYPE_PROTECTION_WINDOW,
)

ATTR_PROTECTION_WINDOW_ENDING_TIME = "end_time"
ATTR_PROTECTION_WINDOW_ENDING_UV = "end_uv"
ATTR_PROTECTION_WINDOW_STARTING_TIME = "start_time"
ATTR_PROTECTION_WINDOW_STARTING_UV = "start_uv"

BINARY_SENSORS = {TYPE_PROTECTION_WINDOW: ("Protection Window", "mdi:sunglasses")}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up an OpenUV sensor based on a config entry."""
    openuv = hass.data[DOMAIN][DATA_CLIENT][entry.entry_id]

    binary_sensors = []
    for kind, attrs in BINARY_SENSORS.items():
        name, icon = attrs
        binary_sensors.append(OpenUvBinarySensor(openuv, kind, name, icon))

    async_add_entities(binary_sensors, True)


class OpenUvBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    def __init__(self, openuv, sensor_type, name, icon):
        """Initialize the sensor."""
        super().__init__(openuv, sensor_type)

        self._attr_icon = icon
        self._attr_name = name

    @callback
    def update_from_latest_data(self):
        """Update the state."""
        data = self.openuv.data[DATA_PROTECTION_WINDOW]

        if not data:
            self._attr_available = False
            return

        self._attr_available = True

        for key in ("from_time", "to_time", "from_uv", "to_uv"):
            if not data.get(key):
                LOGGER.info("Skipping update due to missing data: %s", key)
                return

        if self._sensor_type == TYPE_PROTECTION_WINDOW:
            self._attr_is_on = (
                parse_datetime(data["from_time"])
                <= utcnow()
                <= parse_datetime(data["to_time"])
            )
            self._attr_extra_state_attributes.update(
                {
                    ATTR_PROTECTION_WINDOW_ENDING_TIME: as_local(
                        parse_datetime(data["to_time"])
                    ),
                    ATTR_PROTECTION_WINDOW_ENDING_UV: data["to_uv"],
                    ATTR_PROTECTION_WINDOW_STARTING_UV: data["from_uv"],
                    ATTR_PROTECTION_WINDOW_STARTING_TIME: as_local(
                        parse_datetime(data["from_time"])
                    ),
                }
            )
