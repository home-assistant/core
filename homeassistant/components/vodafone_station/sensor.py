"""Vodafone Station sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfDataRate
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import utcnow

from .const import _LOGGER, DOMAIN, LINE_TYPES
from .coordinator import VodafoneStationRouter

NOT_AVAILABLE: list = ["", "N/A", "0.0.0.0"]


@dataclass
class VodafoneStationBaseEntityDescription:
    """Vodafone Station entity base description."""

    value: Callable[[Any, Any], Any] = lambda val, key: val[key]
    is_suitable: Callable[[dict], bool] = lambda val: True


@dataclass
class VodafoneStationEntityDescription(
    VodafoneStationBaseEntityDescription, SensorEntityDescription
):
    """Vodafone Station entity description."""


def _calculate_uptime(value: dict, key: str) -> datetime:
    """Calculate device uptime."""
    d = int(value[key].split(":")[0])
    h = int(value[key].split(":")[1])
    m = int(value[key].split(":")[2])

    return utcnow() - timedelta(days=d, hours=h, minutes=m)


def _line_connection(value: dict, key: str) -> str | None:
    """Identify line type."""

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
        icon="mdi:earth",
        is_suitable=lambda info: info["wan_ip4_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="wan_ip6_addr",
        translation_key="external_ipv6",
        icon="mdi:earth",
        is_suitable=lambda info: info["wan_ip6_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="vf_internet_key_ip_addr",
        translation_key="external_ip_key",
        icon="mdi:earth",
        is_suitable=lambda info: info["vf_internet_key_ip_addr"] not in NOT_AVAILABLE,
    ),
    VodafoneStationEntityDescription(
        key="inter_ip_address",
        translation_key="active_connection",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:wan",
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
        icon="mdi:new-box",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    VodafoneStationEntityDescription(
        key="phone_num1",
        translation_key="phone_num1",
        icon="mdi:phone",
        is_suitable=lambda info: info["phone_unavailable1"] == "0",
    ),
    VodafoneStationEntityDescription(
        key="phone_num2",
        translation_key="phone_num2",
        icon="mdi:phone",
        is_suitable=lambda info: info["phone_unavailable2"] == "0",
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
        icon="mdi:chip",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda value, key: float(value[key][:-1]),
    ),
    VodafoneStationEntityDescription(
        key="sys_memory_usage",
        translation_key="sys_memory_usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value=lambda value, key: float(value[key][:-1]),
    ),
    VodafoneStationEntityDescription(
        key="sys_reboot_cause",
        translation_key="sys_reboot_cause",
        icon="mdi:restart-alert",
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

        sensors_data = coordinator.data.sensors
        serial_num = sensors_data["sys_serial_number"]
        self.entity_description = description

        self._attr_device_info = DeviceInfo(
            configuration_url=coordinator.api.base_url,
            identifiers={(DOMAIN, serial_num)},
            name=f"Vodafone Station ({serial_num})",
            manufacturer="Vodafone",
            model=sensors_data.get("sys_model_name"),
            hw_version=sensors_data["sys_hardware_version"],
            sw_version=sensors_data["sys_firmware_version"],
        )
        self._attr_unique_id = f"{serial_num}_{description.key}"

    @property
    def native_value(self) -> StateType:
        """Sensor value."""
        return self.entity_description.value(
            self.coordinator.data.sensors, self.entity_description.key
        )
