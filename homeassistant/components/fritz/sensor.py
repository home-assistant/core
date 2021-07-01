"""AVM FRITZ!Box binary sensors."""
from __future__ import annotations

import datetime
import logging
from typing import Callable, TypedDict

from fritzconnection.core.exceptions import FritzConnectionException
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
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
    return status.external_ip


def _retrieve_kib_s_sent_state(status: FritzStatus, last_value: str) -> str:
    """Return upload transmission rate."""
    return round(status.transmission_rate[0] * 8 / 1024, 2)


def _retrieve_kib_s_received_state(status: FritzStatus, last_value: str) -> str:
    """Return download transmission rate."""
    return round(status.transmission_rate[1] * 8 / 1024, 2)


def _retrieve_max_kib_s_sent_state(status: FritzStatus, last_value: str) -> str:
    """Return upload max transmission rate."""
    return round(status.max_bit_rate[0] / 1024, 2)


def _retrieve_max_kib_s_received_state(status: FritzStatus, last_value: str) -> str:
    """Return download max transmission rate."""
    return round(status.max_bit_rate[1] / 1024, 2)


def _retrieve_kb_sent_state(status: FritzStatus, last_value: str) -> str:
    """Return upload total data."""
    return round(status.bytes_sent * 8 / 1024 / 1024, 2)


def _retrieve_kb_received_state(status: FritzStatus, last_value: str) -> str:
    """Return download total data."""
    return round(status.bytes_received * 8 / 1024 / 1024, 2)


class SensorData(TypedDict):
    """Sensor data class."""

    name: str
    device_class: str | None
    state_class: str | None
    unit_of_measurement: str | None
    icon: str | None
    state_provider: Callable


SENSOR_DATA = {
    "external_ip": SensorData(
        name="External IP",
        device_class=None,
        state_class=None,
        unit_of_measurement=None,
        icon="mdi:earth",
        state_provider=_retrieve_external_ip_state,
    ),
    "uptime": SensorData(
        name="Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_class=None,
        unit_of_measurement=None,
        icon=None,
        state_provider=_retrieve_uptime_state,
    ),
    "kib_s_sent": SensorData(
        name="KiB/s sent",
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement="KiB/s",
        icon="mdi:web",
        state_provider=_retrieve_kib_s_sent_state,
    ),
    "kib_s_received": SensorData(
        name="KiB/s received",
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement="KiB/s",
        icon="mdi:web",
        state_provider=_retrieve_kib_s_received_state,
    ),
    "max_kib_s_sent": SensorData(
        name="Max KiB/s sent",
        device_class=None,
        unit_of_measurement="KiB/s",
        icon="mdi:web",
        state_provider=_retrieve_max_kib_s_sent_state,
    ),
    "max_kib_s_received": SensorData(
        name="Max KiB/s received",
        device_class=None,
        unit_of_measurement="KiB/s",
        icon="mdi:web",
        state_provider=_retrieve_max_kib_s_received_state,
    ),
    "mb_sent": SensorData(
        name="MB sent",
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement="MB",
        icon="mdi:web",
        state_provider=_retrieve_kb_sent_state,
    ),
    "mb_received": SensorData(
        name="MB received",
        device_class=None,
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement="MB",
        icon="mdi:web",
        state_provider=_retrieve_kb_received_state,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box sensors")
    fritzbox_tools: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]

    if (
        not fritzbox_tools.connection
        or "WANIPConn1" not in fritzbox_tools.connection.services
    ):
        # Only routers are supported at the moment
        return

    entities = []
    for sensor_type in SENSOR_DATA:
        entities.append(FritzBoxSensor(fritzbox_tools, entry.title, sensor_type))

    if entities:
        async_add_entities(entities, True)


class FritzBoxSensor(FritzBoxBaseEntity, SensorEntity):
    """Define FRITZ!Box connectivity class."""

    def __init__(
        self, fritzbox_tools: FritzBoxTools, device_friendly_name: str, sensor_type: str
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self._sensor_data: SensorData = SENSOR_DATA[sensor_type]
        self._last_value: str | None = None
        self._attr_available = True
        self._attr_device_class = self._sensor_data["device_class"]
        self._attr_icon = self._sensor_data["icon"]
        self._attr_name = f"{device_friendly_name} {self._sensor_data['name']}"
        self._attr_state: str | None = None
        self._attr_state_class = self._sensor_data["state_class"]
        self._attr_unit_of_measurement = self._sensor_data["unit_of_measurement"]
        self._attr_unique_id = f"{fritzbox_tools.unique_id}-{sensor_type}"
        super().__init__(fritzbox_tools, device_friendly_name)

    @property
    def _state_provider(self) -> Callable:
        """Return the state provider for the binary sensor."""
        return self._sensor_data["state_provider"]

    def update(self) -> None:
        """Update data."""
        _LOGGER.debug("Updating FRITZ!Box sensors")

        try:
            status: FritzStatus = self._fritzbox_tools.fritz_status
            self._attr_available = True
        except FritzConnectionException:
            _LOGGER.error("Error getting the state from the FRITZ!Box", exc_info=True)
            self._attr_available = False
            return

        self._attr_state = self._last_value = self._state_provider(
            status, self._last_value
        )
