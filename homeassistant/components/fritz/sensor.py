"""AVM FRITZ!Box binary sensors."""
from __future__ import annotations

import datetime
import logging
from typing import Callable, TypedDict

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEVICE_CLASS_TIMESTAMP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .common import FritzBoxBaseEntity, FritzBoxTools
from .const import DOMAIN, UPTIME_DEVIATION

_LOGGER = logging.getLogger(__name__)


def _retrieve_uptime_state(status: FritzStatus, last_value: str) -> str:
    """Return uptime from device."""
    delta_uptime = utcnow() - datetime.timedelta(seconds=status.uptime)

    if (
        not last_value
        or abs(
            (delta_uptime - datetime.datetime.fromisoformat(last_value)).total_seconds()
        )
        > UPTIME_DEVIATION
    ):
        return delta_uptime.replace(microsecond=0).isoformat()

    return last_value


def _retrieve_external_ip_state(status: FritzStatus, last_value: str) -> str:
    """Return external ip from device."""
    return status.external_ip  # type: ignore[no-any-return]


class SensorData(TypedDict):
    """Sensor data class."""

    name: str
    device_class: str | None
    icon: str | None
    state_provider: Callable


SENSOR_DATA = {
    "external_ip": SensorData(
        name="External IP",
        device_class=None,
        icon="mdi:earth",
        state_provider=_retrieve_external_ip_state,
    ),
    "uptime": SensorData(
        name="Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        icon=None,
        state_provider=_retrieve_uptime_state,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box sensors")
    fritzbox_tools = hass.data[DOMAIN][entry.entry_id]

    if "WANIPConn1" not in fritzbox_tools.connection.services:
        # Only routers are supported at the moment
        return

    for sensor_type in SENSOR_DATA:
        async_add_entities(
            [FritzBoxSensor(fritzbox_tools, entry.title, sensor_type)],
            True,
        )


class FritzBoxSensor(FritzBoxBaseEntity, BinarySensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self, fritzbox_tools: FritzBoxTools, device_friendlyname: str, sensor_type: str
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self._sensor_data: SensorData = SENSOR_DATA[sensor_type]
        self._unique_id = f"{fritzbox_tools.unique_id}-{sensor_type}"
        self._name = f"{device_friendlyname} {self._sensor_data['name']}"
        self._is_available = True
        self._last_value: str | None = None
        self._state: str | None = None
        super().__init__(fritzbox_tools, device_friendlyname)

    @property
    def _state_provider(self) -> Callable:
        """Return the state provider for the binary sensor."""
        return self._sensor_data["state_provider"]

    @property
    def name(self) -> str:
        """Return name."""
        return self._name

    @property
    def device_class(self) -> str | None:
        """Return device class."""
        return self._sensor_data["device_class"]

    @property
    def icon(self) -> str | None:
        """Return icon."""
        return self._sensor_data["icon"]

    @property
    def unique_id(self) -> str:
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
            status: FritzStatus = self._fritzbox_tools.fritzstatus
            self._is_available = True
        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._is_available = False
            return

        self._state = self._last_value = self._state_provider(status, self._last_value)
