"""Binary sensor platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from yoto_api import YotoPlayer

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoPlayerEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class YotoBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Yoto binary sensor entity."""

    is_on_fn: Callable[[YotoPlayer], bool | None]


BINARY_SENSORS: tuple[YotoBinarySensorEntityDescription, ...] = (
    YotoBinarySensorEntityDescription(
        key="charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda player: player.status.is_charging,
    ),
    YotoBinarySensorEntityDescription(
        key="headphones",
        translation_key="headphones",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda player: player.status.is_audio_device_connected,
    ),
    YotoBinarySensorEntityDescription(
        key="bluetooth_audio",
        translation_key="bluetooth_audio",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda player: player.status.is_bluetooth_audio_connected,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto binary sensor platform."""
    coordinator = entry.runtime_data
    known_players: set[str] = set()

    @callback
    def _add_players() -> None:
        current = set(coordinator.data)
        new_players = current - known_players
        known_players.clear()
        known_players.update(current)
        if new_players:
            async_add_entities(
                YotoBinarySensor(coordinator, coordinator.data[player_id], description)
                for player_id in new_players
                for description in BINARY_SENSORS
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_players))
    _add_players()


class YotoBinarySensor(YotoPlayerEntity, BinarySensorEntity):
    """Representation of a Yoto player binary sensor."""

    entity_description: YotoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.is_on_fn(self.player)
