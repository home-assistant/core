"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from pyenphase import (
    EnvoyData,
    EnvoyEncharge,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import EnphaseUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class EnvoyEnchargeRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EnvoyEncharge], bool]


@dataclass
class EnvoyEnchargeBinarySensorEntityDescription(
    BinarySensorEntityDescription, EnvoyEnchargeRequiredKeysMixin
):
    """Describes an Envoy Encharge sensor entity."""


ENCHARGE_SENSORS = (
    EnvoyEnchargeBinarySensorEntityDescription(
        key="communicating",
        translation_key="communicating",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda encharge: encharge.communicating,
    ),
    EnvoyEnchargeBinarySensorEntityDescription(
        key="dc_switch",
        translation_key="dc_switch",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda encharge: not encharge.dc_switch_off,
    ),
    EnvoyEnchargeBinarySensorEntityDescription(
        key="operating",
        translation_key="operating",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda encharge: encharge.operating,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    envoy_data = coordinator.envoy.data
    assert envoy_data is not None
    envoy_serial_num = config_entry.unique_id
    assert envoy_serial_num is not None
    _LOGGER.debug("Envoy data: %s", envoy_data)
    entities: list[Entity] = []
    if envoy_data.encharge_inventory:
        entities.extend(
            EnvoyEnchargeBinarySensorEntity(coordinator, description, encharge)
            for description in ENCHARGE_SENSORS
            for encharge in envoy_data.encharge_inventory
        )

    async_add_entities(entities)


class EnvoyEnchargeBinarySensorEntity(
    CoordinatorEntity[EnphaseUpdateCoordinator], BinarySensorEntity
):
    """Defines a base envoy binary_sensor entity."""

    _attr_has_entity_name = True
    entity_description: EnvoyEnchargeBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EnphaseUpdateCoordinator,
        description: EnvoyEnchargeBinarySensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Init the envoy base entity."""
        self.entity_description = description
        self.coordinator = coordinator
        assert serial_number is not None

        self.envoy_serial_num = coordinator.envoy.serial_number
        assert self.envoy_serial_num is not None

        self._serial_number = serial_number
        self._attr_unique_id = f"{serial_number}_{description.key}"
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            manufacturer="Enphase",
            model="Encharge",
            name=f"Encharge {serial_number}",
            sw_version=str(encharge_inventory[self._serial_number].firmware_version),
            via_device=(DOMAIN, self.envoy_serial_num),
        )

        super().__init__(coordinator)

    @property
    def data(self) -> EnvoyData:
        """Return envoy data."""
        data = self.coordinator.envoy.data
        assert data is not None
        return data

    @property
    def is_on(self) -> bool:
        """Return the state of the Encharge binary_sensor."""
        encharge_inventory = self.data.encharge_inventory
        assert encharge_inventory is not None
        return self.entity_description.value_fn(encharge_inventory[self._serial_number])
