"""Binary Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from lmcloud.models import LaMarzoccoMachineConfig

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoBinarySensorEntityDescription(
    LaMarzoccoEntityDescription,
    BinarySensorEntityDescription,
):
    """Description of a La Marzocco binary sensor."""

    is_on_fn: Callable[[LaMarzoccoMachineConfig], bool]


ENTITIES: tuple[LaMarzoccoBinarySensorEntityDescription, ...] = (
    LaMarzoccoBinarySensorEntityDescription(
        key="water_tank",
        translation_key="water_tank",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda config: not config.water_contact,
        entity_category=EntityCategory.DIAGNOSTIC,
        supported_fn=lambda coordinator: coordinator.local_connection_configured,
    ),
    LaMarzoccoBinarySensorEntityDescription(
        key="brew_active",
        translation_key="brew_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda config: config.brew_active,
        available_fn=lambda device: device.websocket_connected,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoBinarySensorEntityDescription(
        key="backflush_enabled",
        translation_key="backflush_enabled",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=lambda config: config.backflush_enabled,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = entry.runtime_data

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
        return self.entity_description.is_on_fn(self.coordinator.device.config)
