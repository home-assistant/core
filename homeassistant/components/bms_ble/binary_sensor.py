"""Support for BMS_BLE binary sensors."""

from collections.abc import Callable

from aiobmsble import BMSMode, BMSSample

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import ATTR_BATTERY_CHARGING, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BTBmsConfigEntry
from .const import (
    ATTR_BALANCER,
    ATTR_BATTERY_MODE,
    ATTR_CELL_COUNT,
    ATTR_CHRG_MOSFET,
    ATTR_DISCHRG_MOSFET,
    ATTR_HEATER,
    ATTR_PROBLEM,
    DOMAIN,
)
from .coordinator import BTBmsCoordinator

PARALLEL_UPDATES = 0


class BmsBinaryEntityDescription(BinarySensorEntityDescription, frozen_or_thawed=True):
    """Describes BMS sensor entity."""

    attr_fn: Callable[[BMSSample], dict[str, int | str]] | None = None


BINARY_SENSOR_TYPES: list[BmsBinaryEntityDescription] = [
    BmsBinaryEntityDescription(
        attr_fn=lambda data: (
            {
                ATTR_BATTERY_MODE: data.get(
                    ATTR_BATTERY_MODE, BMSMode.UNKNOWN
                ).name.lower()
            }
            if ATTR_BATTERY_MODE in data
            else {}
        ),
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        key=ATTR_BATTERY_CHARGING,
    ),
    BmsBinaryEntityDescription(
        attr_fn=lambda data: (
            {
                "cells": f"{data.get(ATTR_BALANCER, 0):0{data.get(ATTR_CELL_COUNT, 8)}b}"[
                    ::-1
                ]
            }
            if isinstance(data.get(ATTR_BALANCER), int)
            else {}
        ),
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_BALANCER,
        name="Balancer",
        translation_key=ATTR_BALANCER,
    ),
    BmsBinaryEntityDescription(
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_CHRG_MOSFET,
        name="Charge MOSFET",
        translation_key=ATTR_CHRG_MOSFET,
    ),
    BmsBinaryEntityDescription(
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_DISCHRG_MOSFET,
        name="Discharge MOSFET",
        translation_key=ATTR_DISCHRG_MOSFET,
    ),
    BmsBinaryEntityDescription(
        device_class=BinarySensorDeviceClass.HEAT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        key=ATTR_HEATER,
        translation_key=ATTR_HEATER,
    ),
    BmsBinaryEntityDescription(
        attr_fn=lambda data: (
            {"problem_code": data.get("problem_code", 0)}
            if "problem_code" in data
            else {}
        ),
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        key=ATTR_PROBLEM,
    ),
]


async def async_setup_entry(
    _hass: HomeAssistant,
    config_entry: BTBmsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in Home Assistant."""

    bms: BTBmsCoordinator = config_entry.runtime_data
    for descr in BINARY_SENSOR_TYPES:
        if descr.key not in bms.data:
            continue
        async_add_entities(
            [BMSBinarySensor(bms, descr, format_mac(config_entry.unique_id))]
        )


class BMSBinarySensor(CoordinatorEntity[BTBmsCoordinator], BinarySensorEntity):
    """The generic BMS binary sensor implementation."""

    entity_description: BmsBinaryEntityDescription

    def __init__(
        self,
        bms: BTBmsCoordinator,
        descr: BmsBinaryEntityDescription,
        unique_id: str,
    ) -> None:
        """Initialize BMS binary sensor."""
        self._attr_unique_id = f"{DOMAIN}-{unique_id}-{descr.key}"
        self._attr_device_info = bms.device_info
        self._attr_has_entity_name = True
        self.entity_description: BmsBinaryEntityDescription = descr
        super().__init__(bms)

    @property
    def is_on(self) -> bool | None:
        """Handle updated data from the coordinator."""
        return bool(self.coordinator.data.get(self.entity_description.key))

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        """Return entity specific state attributes, e.g. cell voltages."""
        return (
            fn(self.coordinator.data)
            if (fn := self.entity_description.attr_fn)
            else None
        )
