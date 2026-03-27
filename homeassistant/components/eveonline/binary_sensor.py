"""Binary sensor platform for the Eve Online integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import EveOnlineConfigEntry, EveOnlineCoordinator, EveOnlineData
from .entity import EveOnlineCharacterEntity, EveOnlineServerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class EveOnlineBinarySensorDescription(BinarySensorEntityDescription):
    """Describe an Eve Online binary sensor."""

    value_fn: Callable[[EveOnlineData], bool | None]
    available_fn: Callable[[EveOnlineData], bool] = lambda _: True


SERVER_BINARY_SENSORS: tuple[EveOnlineBinarySensorDescription, ...] = (
    EveOnlineBinarySensorDescription(
        key="server_vip",
        translation_key="server_vip",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.server_status.vip,
    ),
)

CHARACTER_BINARY_SENSORS: tuple[EveOnlineBinarySensorDescription, ...] = (
    EveOnlineBinarySensorDescription(
        key="character_online",
        translation_key="character_online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: (
            data.character_online.online if data.character_online else None
        ),
        available_fn=lambda data: data.character_online is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EveOnlineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Eve Online binary sensors from a config entry."""
    coordinator = entry.runtime_data
    entities: list[EveOnlineBinarySensor] = []

    # Only create shared Tranquility server entities for the first loaded entry
    # to avoid duplicate unique_ids when multiple characters are configured.
    if not any(
        e
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ):
        entities.extend(
            EveOnlineServerBinarySensor(coordinator, description)
            for description in SERVER_BINARY_SENSORS
        )

    entities.extend(
        EveOnlineCharacterBinarySensor(coordinator, description)
        for description in CHARACTER_BINARY_SENSORS
    )
    async_add_entities(entities)


class EveOnlineBinarySensor(BinarySensorEntity):
    """Base class for Eve Online binary sensors."""

    entity_description: EveOnlineBinarySensorDescription
    coordinator: EveOnlineCoordinator

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.data)


class EveOnlineServerBinarySensor(EveOnlineServerEntity, EveOnlineBinarySensor):
    """Eve Online server binary sensor (shared Tranquility device)."""

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        description: EveOnlineBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description


class EveOnlineCharacterBinarySensor(EveOnlineCharacterEntity, EveOnlineBinarySensor):
    """Eve Online character binary sensor (per-character device)."""

    def __init__(
        self,
        coordinator: EveOnlineCoordinator,
        description: EveOnlineBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data
        )
