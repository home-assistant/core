"""AVM FRITZ!Box binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
import datetime
import logging
from typing import Any, Callable, Literal

from fritzconnection.core.exceptions import (
    FritzActionError,
    FritzActionFailedError,
    FritzConnectionException,
    FritzInternalError,
    FritzServiceError,
)
from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
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
    return status.noise_margin[0] / 10  # type: ignore[no-any-return]


def _retrieve_link_noise_margin_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download noise margin."""
    return status.noise_margin[1] / 10  # type: ignore[no-any-return]


def _retrieve_link_attenuation_sent_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return upload line attenuation."""
    return status.attenuation[0] / 10  # type: ignore[no-any-return]


def _retrieve_link_attenuation_received_state(
    status: FritzStatus, last_value: str
) -> float:
    """Return download line attenuation."""
    return status.attenuation[1] / 10  # type: ignore[no-any-return]


@dataclass
class FritzRequireKeysMixin:
    """Fritz sensor data class."""

    value_fn: Callable[[FritzStatus, Any], Any]


@dataclass
class FritzSensorEntityDescription(SensorEntityDescription, FritzRequireKeysMixin):
    """Describes Fritz sensor entity."""

    connection_type: Literal["dsl"] | None = None


SENSOR_TYPES: tuple[FritzSensorEntityDescription, ...] = (
    FritzSensorEntityDescription(
        key="external_ip",
        name="External IP",
        icon="mdi:earth",
        value_fn=_retrieve_external_ip_state,
    ),
    FritzSensorEntityDescription(
        key="device_uptime",
        name="Device Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        value_fn=_retrieve_device_uptime_state,
    ),
    FritzSensorEntityDescription(
        key="connection_uptime",
        name="Connection Uptime",
        device_class=DEVICE_CLASS_TIMESTAMP,
        value_fn=_retrieve_connection_uptime_state,
    ),
    FritzSensorEntityDescription(
        key="kb_s_sent",
        name="Upload Throughput",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:upload",
        value_fn=_retrieve_kb_s_sent_state,
    ),
    FritzSensorEntityDescription(
        key="kb_s_received",
        name="Download Throughput",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=DATA_RATE_KILOBYTES_PER_SECOND,
        icon="mdi:download",
        value_fn=_retrieve_kb_s_received_state,
    ),
    FritzSensorEntityDescription(
        key="max_kb_s_sent",
        name="Max Connection Upload Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:upload",
        value_fn=_retrieve_max_kb_s_sent_state,
    ),
    FritzSensorEntityDescription(
        key="max_kb_s_received",
        name="Max Connection Download Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:download",
        value_fn=_retrieve_max_kb_s_received_state,
    ),
    FritzSensorEntityDescription(
        key="gb_sent",
        name="GB sent",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:upload",
        value_fn=_retrieve_gb_sent_state,
    ),
    FritzSensorEntityDescription(
        key="gb_received",
        name="GB received",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        native_unit_of_measurement=DATA_GIGABYTES,
        icon="mdi:download",
        value_fn=_retrieve_gb_received_state,
    ),
    FritzSensorEntityDescription(
        key="link_kb_s_sent",
        name="Link Upload Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:upload",
        value_fn=_retrieve_link_kb_s_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_kb_s_received",
        name="Link Download Throughput",
        native_unit_of_measurement=DATA_RATE_KILOBITS_PER_SECOND,
        icon="mdi:download",
        value_fn=_retrieve_link_kb_s_received_state,
        connection_type=DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_noise_margin_sent",
        name="Link Upload Noise Margin",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:upload",
        value_fn=_retrieve_link_noise_margin_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_noise_margin_received",
        name="Link Download Noise Margin",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:download",
        value_fn=_retrieve_link_noise_margin_received_state,
        connection_type=DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_attenuation_sent",
        name="Link Upload Power Attenuation",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:upload",
        value_fn=_retrieve_link_attenuation_sent_state,
        connection_type=DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_attenuation_received",
        name="Link Download Power Attenuation",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        icon="mdi:download",
        value_fn=_retrieve_link_attenuation_received_state,
        connection_type=DSL_CONNECTION,
    ),
)


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

    dsl: bool = False
    try:
        dslinterface = await hass.async_add_executor_job(
            fritzbox_tools.connection.call_action,
            "WANDSLInterfaceConfig:1",
            "GetInfo",
        )
        dsl = dslinterface["NewEnable"]
    except (
        FritzInternalError,
        FritzActionError,
        FritzActionFailedError,
        FritzServiceError,
    ):
        pass

    entities = [
        FritzBoxSensor(fritzbox_tools, entry.title, description)
        for description in SENSOR_TYPES
        if dsl or description.connection_type != DSL_CONNECTION
    ]

    async_add_entities(entities, True)


class FritzBoxSensor(FritzBoxBaseEntity, SensorEntity):
    """Define FRITZ!Box connectivity class."""

    entity_description: FritzSensorEntityDescription

    def __init__(
        self,
        fritzbox_tools: FritzBoxTools,
        device_friendly_name: str,
        description: FritzSensorEntityDescription,
    ) -> None:
        """Init FRITZ!Box connectivity class."""
        self.entity_description = description
        self._last_device_value: str | None = None
        self._attr_available = True
        self._attr_name = f"{device_friendly_name} {description.name}"
        self._attr_unique_id = f"{fritzbox_tools.unique_id}-{description.key}"
        super().__init__(fritzbox_tools, device_friendly_name)

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

        self._attr_native_value = (
            self._last_device_value
        ) = self.entity_description.value_fn(status, self._last_device_value)
