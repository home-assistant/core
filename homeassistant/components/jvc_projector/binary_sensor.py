"""Binary Sensor platform for JVC Projector integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from jvcprojector import const

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JVCConfigEntry, JvcProjectorDataUpdateCoordinator
from .entity import JvcProjectorEntity


@dataclass(frozen=True, kw_only=True)
class JVCBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe JVC binary sensor entity."""

    value_fn: Callable[[str | None], bool | None] = lambda x: x == "on"
    enabled_default: bool | Callable[[JvcProjectorEntity], bool] = True


JVC_BINARY_SENSORS = (
    JVCBinarySensorEntityDescription(
        key=const.KEY_POWER,
        translation_key="jvc_power",
        device_class=BinarySensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x in (const.ON, const.WARMING) if x is not None else None,
    ),
    JVCBinarySensorEntityDescription(
        key=const.KEY_LOW_LATENCY,
        translation_key="jvc_low_latency_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x == const.ON if x is not None else None,
    ),
    JVCBinarySensorEntityDescription(
        key=const.KEY_ESHIFT,
        translation_key="jvc_eshift",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x == const.ON if x is not None else None,
        enabled_default=JvcProjectorEntity.has_eshift,
    ),
    JVCBinarySensorEntityDescription(
        key=const.KEY_SOURCE,
        translation_key="jvc_source_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda x: x == const.SIGNAL if x is not None else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: JVCConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the JVC Projector binary sensor platform from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        JvcBinarySensor(coordinator, description) for description in JVC_BINARY_SENSORS
    )


class JvcBinarySensor(JvcProjectorEntity, BinarySensorEntity):
    """The entity class for JVC Projector Binary Sensor."""

    entity_description: JVCBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: JvcProjectorDataUpdateCoordinator,
        description: JVCBinarySensorEntityDescription,
    ) -> None:
        """Initialize the JVC Projector binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"
        self._attr_entity_registry_enabled_default = (
            description.enabled_default(self)
            if callable(description.enabled_default)
            else description.enabled_default
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None
        return self.entity_description.value_fn(value)
