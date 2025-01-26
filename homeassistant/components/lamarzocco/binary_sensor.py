"""Binary Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from pylamarzocco.const import MachineModel
from pylamarzocco.models import LaMarzoccoMachineConfig

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import LaMarzoccoConfigEntry
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription, LaMarzoccScaleEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoBinarySensorEntityDescription(
    LaMarzoccoEntityDescription,
    BinarySensorEntityDescription,
):
    """Description of a La Marzocco binary sensor."""

    is_on_fn: Callable[[LaMarzoccoMachineConfig], bool | None]


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

SCALE_ENTITIES: tuple[LaMarzoccoBinarySensorEntityDescription, ...] = (
    LaMarzoccoBinarySensorEntityDescription(
        key="connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        is_on_fn=lambda config: config.scale.connected if config.scale else None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator = entry.runtime_data.config_coordinator

    entities = [
        LaMarzoccoBinarySensorEntity(coordinator, description)
        for description in ENTITIES
        if description.supported_fn(coordinator)
    ]

    if (
        coordinator.device.model == MachineModel.LINEA_MINI
        and coordinator.device.config.scale
    ):
        entities.extend(
            LaMarzoccoScaleBinarySensorEntity(coordinator, description)
            for description in SCALE_ENTITIES
        )

    def _async_add_new_scale() -> None:
        async_add_entities(
            LaMarzoccoScaleBinarySensorEntity(coordinator, description)
            for description in SCALE_ENTITIES
        )

    coordinator.new_device_callback.append(_async_add_new_scale)

    async_add_entities(entities)


class LaMarzoccoBinarySensorEntity(LaMarzoccoEntity, BinarySensorEntity):
    """Binary Sensor representing espresso machine water reservoir status."""

    entity_description: LaMarzoccoBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.device.config)


class LaMarzoccoScaleBinarySensorEntity(
    LaMarzoccoBinarySensorEntity, LaMarzoccScaleEntity
):
    """Binary sensor for La Marzocco scales."""

    entity_description: LaMarzoccoBinarySensorEntityDescription
