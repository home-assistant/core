"""Support for powering relays in a DoorBird video doorbell."""

from collections.abc import Callable
from dataclasses import dataclass

from doorbirdpy import DoorBird

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData

IR_RELAY = "__ir_light__"


@dataclass(frozen=True, kw_only=True)
class DoorbirdButtonEntityDescription(ButtonEntityDescription):
    """Class to describe a Doorbird Button entity."""

    press_action: Callable[[DoorBird, str], None]


RELAY_ENTITY_DESCRIPTION = DoorbirdButtonEntityDescription(
    key="relay",
    translation_key="relay",
    press_action=lambda device, relay: device.energize_relay(relay),
)
IR_ENTITY_DESCRIPTION = DoorbirdButtonEntityDescription(
    key="ir",
    translation_key="ir",
    press_action=lambda device, _: device.turn_light_on(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DoorBird button platform."""
    door_bird_data = config_entry.runtime_data
    relays = door_bird_data.door_station_info["RELAYS"]

    entities = [
        DoorBirdButton(door_bird_data, relay, RELAY_ENTITY_DESCRIPTION)
        for relay in relays
    ]
    entities.append(DoorBirdButton(door_bird_data, IR_RELAY, IR_ENTITY_DESCRIPTION))

    async_add_entities(entities)


class DoorBirdButton(DoorBirdEntity, ButtonEntity):
    """A relay in a DoorBird device."""

    entity_description: DoorbirdButtonEntityDescription

    def __init__(
        self,
        door_bird_data: DoorBirdData,
        relay: str,
        entity_description: DoorbirdButtonEntityDescription,
    ) -> None:
        """Initialize a relay in a DoorBird device."""
        super().__init__(door_bird_data)
        self._relay = relay
        self.entity_description = entity_description
        if self._relay == IR_RELAY:
            self._attr_name = "IR"
        else:
            self._attr_name = f"Relay {self._relay}"
        self._attr_unique_id = f"{self._mac_addr}_{self._relay}"

    def press(self) -> None:
        """Power the relay."""
        self.entity_description.press_action(self._door_station.device, self._relay)
