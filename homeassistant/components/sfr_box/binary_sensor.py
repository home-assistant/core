"""SFR Box sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sfrbox_api.models import DslInfo, FtthInfo, WanInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SFRConfigEntry
from .entity import SFRCoordinatorEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


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
    hass: HomeAssistant,
    entry: SFRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    data = entry.runtime_data
    system_info = data.system.data
    if TYPE_CHECKING:
        assert system_info is not None

    entities: list[SFRBoxBinarySensor] = [
        SFRBoxBinarySensor(data.wan, description, system_info)
        for description in WAN_SENSOR_TYPES
    ]
    if (net_infra := system_info.net_infra) == "adsl":
        entities.extend(
            SFRBoxBinarySensor(data.dsl, description, system_info)
            for description in DSL_SENSOR_TYPES
        )
    elif net_infra == "ftth":
        entities.extend(
            SFRBoxBinarySensor(data.ftth, description, system_info)
            for description in FTTH_SENSOR_TYPES
        )

    async_add_entities(entities)


class SFRBoxBinarySensor[_T](SFRCoordinatorEntity[_T], BinarySensorEntity):
    """SFR Box binary sensor."""

    entity_description: SFRBoxBinarySensorEntityDescription[_T]

    @property
    def is_on(self) -> bool | None:
        """Return the native value of the device."""
        return self.entity_description.value_fn(self.coordinator.data)
