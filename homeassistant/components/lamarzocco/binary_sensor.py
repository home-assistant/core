"""Binary Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from lmcloud.lm_machine import LaMarzoccoMachine

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoBinarySensorEntityDescription(
    LaMarzoccoEntityDescription,
    BinarySensorEntityDescription,
):
    """Description of a La Marzocco binary sensor."""

    is_on_fn: Callable[[LaMarzoccoMachine], bool]


ENTITIES: tuple[LaMarzoccoBinarySensorEntityDescription, ...] = (
    LaMarzoccoBinarySensorEntityDescription(
        key="water_tank",
        translation_key="water_tank",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda device: not device.config.water_contact,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda coordinator: coordinator.local_connection_configured,
    ),
    LaMarzoccoBinarySensorEntityDescription(
        key="brew_active",
        translation_key="brew_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda device: device.config.brew_active,
        available_fn=lambda device: device.websocket_connected,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        LaMarzoccoBinarySensorEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    )


class LaMarzoccoBinarySensorEntity(LaMarzoccoEntity, BinarySensorEntity):
    """Binary Sensor representing espresso machine water reservoir status."""

    entity_description: LaMarzoccoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.device)
