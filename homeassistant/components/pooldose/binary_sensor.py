"""Binary sensors for the Seko PoolDose integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, cast

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .entity import PooldoseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PooldoseBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes PoolDose binary sensor entity."""


BINARY_SENSOR_DESCRIPTIONS: tuple[PooldoseBinarySensorEntityDescription, ...] = (
    PooldoseBinarySensorEntityDescription(
        key="pump_alarm",
        translation_key="pump_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="ph_level_alarm",
        translation_key="ph_level_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="orp_level_alarm",
        translation_key="orp_level_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="flow_rate_alarm",
        translation_key="flow_rate_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="alarm_ofa_ph",
        translation_key="alarm_ofa_ph",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="alarm_ofa_orp",
        translation_key="alarm_ofa_orp",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="alarm_ofa_cl",
        translation_key="alarm_ofa_cl",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="relay_alarm",
        translation_key="relay_alarm",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PooldoseBinarySensorEntityDescription(
        key="relay_aux1",
        translation_key="relay_aux1",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseBinarySensorEntityDescription(
        key="relay_aux2",
        translation_key="relay_aux2",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PooldoseBinarySensorEntityDescription(
        key="relay_aux3",
        translation_key="relay_aux3",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose binary sensor entities from a config entry."""
    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    coordinator = config_entry.runtime_data
    binary_sensor_data = coordinator.data["binary_sensor"]
    serial_number = config_entry.unique_id

    async_add_entities(
        PooldoseBinarySensor(
            coordinator,
            serial_number,
            coordinator.device_info,
            description,
            "binary_sensor",
        )
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.key in binary_sensor_data
    )


class PooldoseBinarySensor(PooldoseEntity, BinarySensorEntity):
    """Binary sensor entity for the Seko PoolDose Python API."""

    entity_description: PooldoseBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        data = cast(dict, self.get_data())
        return cast(bool, data["value"])
