"""Support for OpenUV binary sensors."""
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from homeassistant.util.dt import as_local, parse_datetime, utcnow

from . import (
    DATA_OPENUV_CLIENT,
    DATA_PROTECTION_WINDOW,
    DOMAIN,
    TYPE_PROTECTION_WINDOW,
    OpenUvEntity,
)

_LOGGER = logging.getLogger(__name__)

ATTR_PROTECTION_WINDOW_ENDING_TIME = "end_time"
ATTR_PROTECTION_WINDOW_ENDING_UV = "end_uv"
ATTR_PROTECTION_WINDOW_STARTING_TIME = "start_time"
ATTR_PROTECTION_WINDOW_STARTING_UV = "start_uv"

BINARY_SENSORS = {TYPE_PROTECTION_WINDOW: ("Protection Window", "mdi:sunglasses")}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up an OpenUV sensor based on a config entry."""
    openuv = hass.data[DOMAIN][DATA_OPENUV_CLIENT][entry.entry_id]

    binary_sensors = []
    for kind, attrs in BINARY_SENSORS.items():
        name, icon = attrs
        binary_sensors.append(
            OpenUvBinarySensor(openuv, kind, name, icon, entry.entry_id)
        )

    async_add_entities(binary_sensors, True)


class OpenUvBinarySensor(OpenUvEntity, BinarySensorEntity):
    """Define a binary sensor for OpenUV."""

    def __init__(self, openuv, sensor_type, name, icon, entry_id):
        """Initialize the sensor."""
        super().__init__(openuv)

        self._async_unsub_dispatcher_connect = None
        self._entry_id = entry_id
        self._icon = icon
        self._latitude = openuv.client.latitude
        self._longitude = openuv.client.longitude
        self._name = name
        self._sensor_type = sensor_type
        self._state = None

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self._latitude}_{self._longitude}_{self._sensor_type}"

    @callback
    def update_from_latest_data(self):
        """Update the state."""
        data = self.openuv.data[DATA_PROTECTION_WINDOW]

        if not data:
            self._available = False
            return

        self._available = True

        for key in ("from_time", "to_time", "from_uv", "to_uv"):
            if not data.get(key):
                _LOGGER.info("Skipping update due to missing data: %s", key)
                return

        if self._sensor_type == TYPE_PROTECTION_WINDOW:
            self._state = (
                parse_datetime(data["from_time"])
                <= utcnow()
                <= parse_datetime(data["to_time"])
            )
            self._attrs.update(
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
