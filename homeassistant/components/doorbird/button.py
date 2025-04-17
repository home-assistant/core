"""Support for relays and actions in a DoorBird video doorbell."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, replace
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .device import ConfiguredDoorBird, async_reset_device_favorites
from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData

IR_RELAY = "__ir_light__"


@dataclass(frozen=True, kw_only=True)
class DoorbirdButtonEntityDescription(ButtonEntityDescription):
    """Class to describe a Doorbird Button entity."""

    press_action: Callable[[ConfiguredDoorBird, str], Coroutine[Any, Any, bool | None]]


RELAY_ENTITY_DESCRIPTION = DoorbirdButtonEntityDescription(
    key="relay",
    press_action=lambda door_station, relay: door_station.device.energize_relay(relay),
)
BUTTON_DESCRIPTIONS: tuple[DoorbirdButtonEntityDescription, ...] = (
    DoorbirdButtonEntityDescription(
        key="__ir_light__",
        translation_key="ir",
        press_action=lambda door_station, _: door_station.device.turn_light_on(),
    ),
    DoorbirdButtonEntityDescription(
        key="reset_favorites",
        translation_key="reset_favorites",
        press_action=lambda door_station, _: async_reset_device_favorites(door_station),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DoorBird button platform."""
    door_bird_data = config_entry.runtime_data
    relays: list[str] = door_bird_data.door_station_info["RELAYS"]
    entities = [
        DoorBirdButton(
            door_bird_data,
            replace(RELAY_ENTITY_DESCRIPTION, name=f"Relay {relay}"),
            relay,
        )
        for relay in relays
    ]
    entities.extend(
        DoorBirdButton(door_bird_data, button_description)
        for button_description in BUTTON_DESCRIPTIONS
    )
    async_add_entities(entities)


class DoorBirdButton(DoorBirdEntity, ButtonEntity):
    """A button for a DoorBird device."""

    entity_description: DoorbirdButtonEntityDescription

    def __init__(
        self,
        door_bird_data: DoorBirdData,
        entity_description: DoorbirdButtonEntityDescription,
        relay: str | None = None,
    ) -> None:
        """Initialize a button for a DoorBird device."""
        super().__init__(door_bird_data)
        self._relay = relay or ""
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._mac_addr}_{relay or entity_description.key}"

    async def async_press(self) -> None:
        """Call the press action."""
        await self.entity_description.press_action(self._door_station, self._relay)
