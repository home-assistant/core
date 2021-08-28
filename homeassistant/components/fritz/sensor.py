"""AVM FRITZ!Box binary sensors."""
from __future__ import annotations

import datetime
import logging
from typing import Callable, TypedDict

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzServiceError,
)
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DATA_GIGABYTES,
    DATA_RATE_KILOBITS_PER_SECOND,
    DATA_RATE_KILOBYTES_PER_SECOND,
    DEVICE_CLASS_TIMESTAMP,
    SIGNAL_STRENGTH_DECIBELS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utcnow

from .common import FritzBoxBaseEntity, FritzBoxTools
from .const import DOMAIN, DSL_CONNECTION, UPTIME_DEVIATION

_LOGGER = logging.getLogger(__name__)


def _uptime_calculation(seconds_uptime: float, last_value: str | None) -> str:
    """Calculate uptime with deviation."""
    delta_uptime = utcnow() - datetime.timedelta(seconds=seconds_uptime)

    if (
        not last_value
        or abs(
            (delta_uptime - datetime.datetime.fromisoformat(last_value)).total_seconds()
        )
        > UPTIME_DEVIATION
    ):
        return delta_uptime.replace(microsecond=0).isoformat()

    return last_value


def _retrieve_device_uptime_state(status: FritzStatus, last_value: str) -> str:
    """Return uptime from device."""
    return _uptime_calculation(status.device_uptime, last_value)


def _retrieve_connection_uptime_state(
    status: FritzStatus, last_value: str | None
) -> str:
    """Return uptime from connection."""
    return _uptime_calculation(status.connection_uptime, last_value)


def _retrieve_external_ip_state(status: FritzStatus, last_value: str) -> str:
    """Return external ip from device."""
    return status.external_ip  # type: ignore[no-any-return]


def _retrieve_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload transmission rate."""
    return round(status.transmission_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download transmission rate."""
    return round(status.transmission_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_max_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload max transmission rate."""
    return round(status.max_bit_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_max_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download max transmission rate."""
    return round(status.max_bit_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_gb_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload total data."""
    return round(status.bytes_sent / 1000 / 1000 / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_gb_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download total data."""
    return round(status.bytes_received / 1000 / 1000 / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_kb_s_sent_state(status: FritzStatus, last_value: str) -> float:
    """Return upload link rate."""
    return round(status.max_linked_bit_rate[0] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_kb_s_received_state(status: FritzStatus, last_value: str) -> float:
    """Return download link rate."""
    return round(status.max_linked_bit_rate[1] / 1000, 1)  # type: ignore[no-any-return]


def _retrieve_link_noise_margin_sent_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return upload noise margin."""
    return status.noise_margin[0]  # type: ignore[no-any-return]


def _retrieve_link_noise_margin_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download noise margin."""
    return status.noise_margin[1]  # type: ignore[no-any-return]


def _retrieve_link_attenuation_sent_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return upload line attenuation."""
    return status.attenuation[0]  # type: ignore[no-any-return]


def _retrieve_link_attenuation_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download line attenuation."""
    return status.attenuation[1]  # type: ignore[no-any-return]


class SensorData(TypedDict, total=False):
    """Sensor data class."""

    name: str
    device_class: str | None
    state_class: str | None
    unit_of_measurement: str | None
    icon: str | None
    state_provider: Callable
    connection_type: str | None


SENSOR_DATA = {
    "external_ip": SensorData(
        name="External IP",
        icon="mdi:earth",
        state_provider=_retrieve_external_ip_state,
    ),
    "device_uptime": SensorData(
        name="Device Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_provider=_retrieve_device_uptime_state,
    ),
    "connection_uptime": SensorData(
        name="Connection Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_provider=_retrieve_connection_uptime_state,
    ),
    "kb_s_sent": SensorData(
        name="Upload Throughput",
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:upload",
        state_provider=_retrieve_kb_s_sent_state,
    ),
    "kb_s_received": SensorData(
        name="Download Throughput",
        state_class=STATE_CLASS_MEASUREMENT,
        unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:download",
        state_provider=_retrieve_kb_s_received_state,
    ),
    "max_kb_s_sent": SensorData(
        name="Max Connection Upload Throughput",
        unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:upload",
        state_provider=_retrieve_max_kb_s_sent_state,
    ),
    "max_kb_s_received": SensorData(
        name="Max Connection Download Throughput",
        unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:download",
        state_provider=_retrieve_max_kb_s_received_state,
    ),
    "gb_sent": SensorData(
        name="GB sent",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:upload",
        state_provider=_retrieve_gb_sent_state,
    ),
    "gb_received": SensorData(
        name="GB received",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
        state_provider=_retrieve_gb_received_state,
    ),
    "link_kb_s_sent": SensorData(
        name="Link Upload Throughput",
        unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:upload",
        state_provider=_retrieve_link_kb_s_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    "link_kb_s_received": SensorData(
        name="Link Download Throughput",
        unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:download",
        state_provider=_retrieve_link_kb_s_received_state,
        connection_type=DSL_CONNECTION,
    ),
    "link_noise_margin_sent": SensorData(
        name="Link Upload Noise Margin",
        unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:upload",
        state_provider=_retrieve_link_noise_margin_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    "link_noise_margin_received": SensorData(
        name="Link Download Noise Margin",
        unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:download",
        state_provider=_retrieve_link_noise_margin_received_state,
        connection_type=DSL_CONNECTION,
    ),
    "link_attenuation_sent": SensorData(
        name="Link Upload Power Attenuation",
        unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:upload",
        state_provider=_retrieve_link_attenuation_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    "link_attenuation_received": SensorData(
        name="Link Download Power Attenuation",
        unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:download",
        state_provider=_retrieve_link_attenuation_received_state,
        connection_type=DSL_CONNECTION,
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
    dsl: bool = False
    try:
        dslinterface = await hass.async_add_executor_job(
            fritzbox_tools.connection.call_action,
            "WANDSLInterfaceConfig:1",
            "GetInfo",
        )
        dsl = dslinterface["NewEnable"]
    except (FritzActionError, FritzActionFailedError, FritzServiceError):
        pass

    for sensor_type, sensor_data in SENSOR_DATA.items():
        if not dsl and sensor_data.get("connection_type") == DSL_CONNECTION:
            continue
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
        self._last_device_value: str | None = None
        self._attr_available = True
        self._attr_device_class = self._sensor_data.get("device_class")
        self._attr_icon = self._sensor_data.get("icon")
        self._attr_name = f"{device_friendly_name} {self._sensor_data['name']}"
        self._attr_state_class = self._sensor_data.get("state_class")
        self._attr_native_unit_of_measurement = self._sensor_data.get(
            "unit_of_measurement"
        )
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

        self._attr_native_value = self._last_device_value = self._state_provider(
            status, self._last_device_value
        )
