"""AVM FRITZ!Box binary sensors."""
from __future__ import annotations

import datetime
import logging

from fritzconnection.core.exceptions import FritzConnectionException

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .common import FritzBoxBaseEntity, FritzBoxTools
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def _retrieve_uptime_state(status, last_value):
    """Return uptime from device."""
    return get_device_uptime(status.uptime, last_value)


def _retrieve_external_ip_state(status, last_value):
    """Return external ip from device."""
    return status.external_ip


SENSOR_NAME = 0
SENSOR_DEVICE_CLASS = 1
SENSOR_ICON = 2
SENSOR_STATE_PROVIDER = 3

# sensor_type: [name, device_class, icon, state_provider]
SENSOR_TYPES_FRITZ = {
    "fritz_external_ip": [
        "External IP",
        None,
        "mdi:earth",
        _retrieve_external_ip_state,
    ],
    "fritz_uptime": ["Uptime", DEVICE_CLASS_TIMESTAMP, None, _retrieve_uptime_state],
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box sensors")
    fritzbox_tools = hass.data[DOMAIN][entry.entry_id]

    if "WANIPConn1" in fritzbox_tools.connection.services:
        # Only routers are supported at the moment

        for sensor_type in SENSOR_TYPES_FRITZ:
            async_add_entities(
                [
                    FritzBoxSensor(
                        fritzbox_tools, entry.title, SENSOR_TYPES_FRITZ[sensor_type]
                    )
                ],
                True,
            )


class FritzBoxSensor(FritzBoxBaseEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self, fritzbox_tools: FritzBoxTools, device_friendlyname: str, sensor_type: str
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self._sensor_type = sensor_type
        self._unique_id = f"{fritzbox_tools.unique_id}-{self._sensor_type[SENSOR_NAME].replace(' ', '_').lower()}"
        self._name = f"{device_friendlyname} {self._sensor_type[SENSOR_NAME]}"
        self._is_available = True
        self._last_value: str | None = None
        self._state: str | None = None
        super().__init__(fritzbox_tools, device_friendlyname)

    @property
    def _state_provider(self):
        """Return the state provider for the binary sensor."""
        return self._sensor_type[SENSOR_STATE_PROVIDER]

    @property
    def name(self):
        """Return name."""
        return self._name

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self._sensor_type[SENSOR_DEVICE_CLASS]

    @property
    def icon(self):
        """Return icon."""
        return self._sensor_type[SENSOR_ICON]

    @property
    def unique_id(self):
        """Return unique id."""
        return self._unique_id

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return availability."""
        return self._is_available

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box sensors")

        try:
            status = self._fritzbox_tools.fritzstatus
            self._is_available = True

            self._state = self._last_value = self._state_provider(
                status, self._last_value
            )

        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._is_available = False


def get_device_uptime(uptime: int, last_uptime: str | None) -> str:
    """Return device uptime string, tolerate up to 5 seconds deviation."""
    delta_uptime = utcnow() - datetime.timedelta(seconds=uptime)

    if (
        not last_uptime
        or abs(
            (
                delta_uptime - datetime.datetime.fromisoformat(last_uptime)
            ).total_seconds()
        )
        > 5
    ):
        return delta_uptime.replace(microsecond=0).isoformat()

    return last_uptime
