"""AVM FRITZ!Box binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from fritzconnection.lib.fritzstatus import FritzStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfDataRate,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow

from .common import (
    AvmWrapper,
    ConnectionInfo,
    FritzBoxBaseCoordinatorEntity,
    FritzEntityDescription,
)
from .const import DOMAIN, DSL_CONNECTION, UPTIME_DEVIATION

_LOGGER = logging.getLogger(__name__)


def _uptime_calculation(seconds_uptime: float, last_value: datetime | None) -> datetime:
    """Calculate uptime with deviation."""
    delta_uptime = utcnow() - timedelta(seconds=seconds_uptime)

    if (
        not last_value
        or abs((delta_uptime - last_value).total_seconds()) > UPTIME_DEVIATION
    ):
        return delta_uptime

    return last_value


def _retrieve_device_uptime_state(
    status: FritzStatus, last_value: datetime
) -> datetime:
    """Return uptime from device."""
    return _uptime_calculation(status.device_uptime, last_value)


def _retrieve_connection_uptime_state(
    status: FritzStatus, last_value: datetime | None
) -> datetime:
    """Return uptime from connection."""
    return _uptime_calculation(status.connection_uptime, last_value)


def _retrieve_external_ip_state(status: FritzStatus, last_value: str) -> str:
    """Return external ip from device."""
    return status.external_ip  # type: ignore[no-any-return]


def _retrieve_external_ipv6_state(status: FritzStatus, last_value: str) -> str:
    """Return external ipv6 from device."""
    return str(status.external_ipv6)


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


@dataclass(frozen=True)
class FritzSensorEntityDescription(SensorEntityDescription, FritzEntityDescription):
    """Describes Fritz sensor entity."""

    is_suitable: Callable[[ConnectionInfo], bool] = lambda info: info.wan_enabled


SENSOR_TYPES: tuple[FritzSensorEntityDescription, ...] = (
    FritzSensorEntityDescription(
        key="external_ip",
        translation_key="external_ip",
        value_fn=_retrieve_external_ip_state,
    ),
    FritzSensorEntityDescription(
        key="external_ipv6",
        translation_key="external_ipv6",
        value_fn=_retrieve_external_ipv6_state,
        is_suitable=lambda info: info.ipv6_active,
    ),
    FritzSensorEntityDescription(
        key="device_uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_device_uptime_state,
        is_suitable=lambda info: True,
    ),
    FritzSensorEntityDescription(
        key="connection_uptime",
        translation_key="connection_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_connection_uptime_state,
    ),
    FritzSensorEntityDescription(
        key="kb_s_sent",
        translation_key="kb_s_sent",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_kb_s_sent_state,
    ),
    FritzSensorEntityDescription(
        key="kb_s_received",
        translation_key="kb_s_received",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_kb_s_received_state,
    ),
    FritzSensorEntityDescription(
        key="max_kb_s_sent",
        translation_key="max_kb_s_sent",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_max_kb_s_sent_state,
    ),
    FritzSensorEntityDescription(
        key="max_kb_s_received",
        translation_key="max_kb_s_received",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_retrieve_max_kb_s_received_state,
    ),
    FritzSensorEntityDescription(
        key="gb_sent",
        translation_key="gb_sent",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=_retrieve_gb_sent_state,
    ),
    FritzSensorEntityDescription(
        key="gb_received",
        translation_key="gb_received",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        value_fn=_retrieve_gb_received_state,
    ),
    FritzSensorEntityDescription(
        key="link_kb_s_sent",
        translation_key="link_kb_s_sent",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_link_kb_s_sent_state,
    ),
    FritzSensorEntityDescription(
        key="link_kb_s_received",
        translation_key="link_kb_s_received",
        native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        value_fn=_retrieve_link_kb_s_received_state,
    ),
    FritzSensorEntityDescription(
        key="link_noise_margin_sent",
        translation_key="link_noise_margin_sent",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=_retrieve_link_noise_margin_sent_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_noise_margin_received",
        translation_key="link_noise_margin_received",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=_retrieve_link_noise_margin_received_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_attenuation_sent",
        translation_key="link_attenuation_sent",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=_retrieve_link_attenuation_sent_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
    FritzSensorEntityDescription(
        key="link_attenuation_received",
        translation_key="link_attenuation_received",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        value_fn=_retrieve_link_attenuation_received_state,
        is_suitable=lambda info: info.wan_enabled and info.connection == DSL_CONNECTION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up FRITZ!Box sensors")
    avm_wrapper: AvmWrapper = hass.data[DOMAIN][entry.entry_id]

    connection_info = await avm_wrapper.async_get_connection_info()

    entities = [
        FritzBoxSensor(avm_wrapper, entry.title, description)
        for description in SENSOR_TYPES
        if description.is_suitable(connection_info)
    ]

    async_add_entities(entities)


class FritzBoxSensor(FritzBoxBaseCoordinatorEntity, SensorEntity):
    """Define FRITZ!Box connectivity class."""

    entity_description: FritzSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data["entity_states"].get(self.entity_description.key)
