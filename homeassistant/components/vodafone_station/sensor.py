"""Vodafone Station sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import _LOGGER, DOMAIN, LINE_TYPES
from .coordinator import VodafoneStationRouter

NOT_AVAILABLE: list = ["", "N/A", "0.0.0.0"]
UPTIME_DEVIATION = 60


@dataclass(frozen=True, kw_only=True)
class VodafoneStationEntityDescription(SensorEntityDescription):
    """Vodafone Station entity description."""

    value: Callable[
        [VodafoneStationRouter, str | datetime | float | None, str],
        str | datetime | float | None,
    ] = lambda coordinator, last_value, key: coordinator.data.sensors[key]
    is_suitable: Callable[[dict], bool] = lambda val: True


def _calculate_uptime(
    coordinator: VodafoneStationRouter,
    last_value: str | datetime | float | None,
    key: str,
) -> datetime:
    """Calculate device uptime."""

    delta_uptime = coordinator.api.convert_uptime(coordinator.data.sensors[key])

    if (
        not isinstance(last_value, datetime)
        or abs((delta_uptime - last_value).total_seconds()) > UPTIME_DEVIATION
    ):
        return delta_uptime

    return last_value


def _line_connection(
    coordinator: VodafoneStationRouter,
    last_value: str | datetime | float | None,
    key: str,
) -> str | None:
    """Identify line type."""

    value = coordinator.data.sensors
    internet_ip = value[key]
    dsl_ip = value.get("dsl_ipaddr")
    fiber_ip = value.get("fiber_ipaddr")
    internet_key_ip = value.get("vf_internet_key_ip_addr")

    if internet_ip == dsl_ip:
        return LINE_TYPES[0]

    if internet_ip == fiber_ip:
        return LINE_TYPES[1]

    if internet_ip == internet_key_ip:
        return LINE_TYPES[2]

    return None


SENSOR_TYPES: Final = (
    VodafoneStationEntityDescription(
        key="wan_ip4_addr",
        translation_key="external_ipv4",
        is_suitable=lambda info: info["wan_ip4_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="wan_ip6_addr",
        translation_key="external_ipv6",
        is_suitable=lambda info: info["wan_ip6_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="vf_internet_key_ip_addr",
        translation_key="external_ip_key",
        is_suitable=lambda info: info["vf_internet_key_ip_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="inter_ip_address",
        translation_key="active_connection",
        device_class=SensorDeviceClass.ENUM,
        options=LINE_TYPES,
        value=_line_connection,
    ),
    VodafoneStationEntityDescription(
        key="down_str",
        translation_key="down_stream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VodafoneStationEntityDescription(
        key="up_str",
        translation_key="up_stream",
        device_class=SensorDeviceClass.DATA_RATE,
        native_unit_of_measurement=UnitOfDataRate.KILOBYTES_PER_SECOND,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VodafoneStationEntityDescription(
        key="fw_version",
        translation_key="fw_version",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VodafoneStationEntityDescription(
        key="phone_num1",
        translation_key="phone_num1",
        is_suitable=lambda info: info["phone_num1"] != "",
    ),
    VodafoneStationEntityDescription(
        key="phone_num2",
        translation_key="phone_num2",
        is_suitable=lambda info: info["phone_num2"] != "",
    ),
    VodafoneStationEntityDescription(
        key="sys_uptime",
        translation_key="sys_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=_calculate_uptime,
    ),
    VodafoneStationEntityDescription(
        key="sys_cpu_usage",
        translation_key="sys_cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, last_value, key: float(
            coordinator.data.sensors[key][:-1]
        ),
    ),
    VodafoneStationEntityDescription(
        key="sys_memory_usage",
        translation_key="sys_memory_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda coordinator, last_value, key: float(
            coordinator.data.sensors[key][:-1]
        ),
    ),
    VodafoneStationEntityDescription(
        key="sys_reboot_cause",
        translation_key="sys_reboot_cause",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up entry."""
    _LOGGER.debug("Setting up Vodafone Station sensors")

    coordinator: VodafoneStationRouter = hass.data[DOMAIN][entry.entry_id]

    sensors_data = coordinator.data.sensors

    async_add_entities(
        VodafoneStationSensorEntity(coordinator, sensor_descr)
        for sensor_descr in SENSOR_TYPES
        if sensor_descr.key in sensors_data and sensor_descr.is_suitable(sensors_data)
    )


class VodafoneStationSensorEntity(
    CoordinatorEntity[VodafoneStationRouter], SensorEntity
):
    """Representation of a Vodafone Station sensor."""

    _attr_has_entity_name = True
    entity_description: VodafoneStationEntityDescription

    def __init__(
        self,
        coordinator: VodafoneStationRouter,
        description: VodafoneStationEntityDescription,
    ) -> None:
        """Initialize a Vodafone Station sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"
        self._old_state: str | datetime | float | None = None

    @property
    def native_value(self) -> str | datetime | float | None:
        """Sensor value."""
        self._old_state = self.entity_description.value(
            self.coordinator, self._old_state, self.entity_description.key
        )
        return self._old_state
