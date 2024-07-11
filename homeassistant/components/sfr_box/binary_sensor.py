"""SFR Box sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sfrbox_api.models import DslInfo, FtthInfo, SystemInfo, WanInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SFRDataUpdateCoordinator
from .models import DomainData


@dataclass(frozen=True, kw_only=True)
class SFRBoxBinarySensorEntityDescription[_T](BinarySensorEntityDescription):
    """Description for SFR Box binary sensors."""

    value_fn: Callable[[_T], bool | None]


DSL_SENSOR_TYPES: tuple[SFRBoxBinarySensorEntityDescription[DslInfo], ...] = (
    SFRBoxBinarySensorEntityDescription[DslInfo](
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.status == "up",
        translation_key="dsl_status",
    ),
)
FTTH_SENSOR_TYPES: tuple[SFRBoxBinarySensorEntityDescription[FtthInfo], ...] = (
    SFRBoxBinarySensorEntityDescription[FtthInfo](
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.status == "up",
        translation_key="ftth_status",
    ),
)
WAN_SENSOR_TYPES: tuple[SFRBoxBinarySensorEntityDescription[WanInfo], ...] = (
    SFRBoxBinarySensorEntityDescription[WanInfo](
        key="status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x.status == "up",
        translation_key="wan_status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    entities: list[SFRBoxBinarySensor] = [
        SFRBoxBinarySensor(data.wan, description, data.system.data)
        for description in WAN_SENSOR_TYPES
    ]
    if (net_infra := data.system.data.net_infra) == "adsl":
        entities.extend(
            SFRBoxBinarySensor(data.dsl, description, data.system.data)
            for description in DSL_SENSOR_TYPES
        )
    elif net_infra == "ftth":
        entities.extend(
            SFRBoxBinarySensor(data.ftth, description, data.system.data)
            for description in FTTH_SENSOR_TYPES
        )

    async_add_entities(entities)


class SFRBoxBinarySensor[_T](
    CoordinatorEntity[SFRDataUpdateCoordinator[_T]], BinarySensorEntity
):
    """SFR Box sensor."""

    entity_description: SFRBoxBinarySensorEntityDescription[_T]
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SFRDataUpdateCoordinator[_T],
        description: SFRBoxBinarySensorEntityDescription,
        system_info: SystemInfo,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{system_info.mac_addr}_{coordinator.name}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, system_info.mac_addr)},
        )

    @property
    def is_on(self) -> bool | None:
        """Return the native value of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
