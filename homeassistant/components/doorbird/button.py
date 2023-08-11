"""Support for powering relays in a DoorBird video doorbell."""

from collections.abc import Callable
from dataclasses import dataclass

from doorbirdpy import DoorBird

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DOOR_STATION, DOOR_STATION_INFO
from .entity import DoorBirdEntity

IR_RELAY = "__ir_light__"


@dataclass
class DoorbirdButtonEntityDescriptionMixin:
    """Mixin to describe a Doorbird Button entity."""

    press_action: Callable[[DoorBird, str], None]


@dataclass
class DoorbirdButtonEntityDescription(
    ButtonEntityDescription, DoorbirdButtonEntityDescriptionMixin
):
    """Class to describe a Doorbird Button entity."""


RELAY_ENTITY_DESCRIPTION = DoorbirdButtonEntityDescription(
    key="relay",
    press_action=lambda device, relay: device.energize_relay(relay),
    icon="mdi:dip-switch",
)
IR_ENTITY_DESCRIPTION = DoorbirdButtonEntityDescription(
    key="ir",
    press_action=lambda device, _: device.turn_light_on(),
    icon="mdi:lightbulb",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DoorBird button platform."""
    config_entry_id = config_entry.entry_id

    data = hass.data[DOMAIN][config_entry_id]
    doorstation = data[DOOR_STATION]
    doorstation_info = data[DOOR_STATION_INFO]

    relays = doorstation_info["RELAYS"]

    entities = [
        DoorBirdButton(doorstation, doorstation_info, relay, RELAY_ENTITY_DESCRIPTION)
        for relay in relays
    ]
    entities.append(
        DoorBirdButton(doorstation, doorstation_info, IR_RELAY, IR_ENTITY_DESCRIPTION)
    )

    async_add_entities(entities)


class DoorBirdButton(DoorBirdEntity, ButtonEntity):
    """A relay in a DoorBird device."""

    entity_description: DoorbirdButtonEntityDescription

    def __init__(
        self,
        doorstation: DoorBird,
        doorstation_info,
        relay: str,
        entity_description: DoorbirdButtonEntityDescription,
    ) -> None:
        """Initialize a relay in a DoorBird device."""
        super().__init__(doorstation, doorstation_info)
        self._relay = relay
        self.entity_description = entity_description

        if self._relay == IR_RELAY:
            self._attr_name = "IR"
        else:
            self._attr_name = f"Relay {self._relay}"
        self._attr_unique_id = f"{self._mac_addr}_{self._relay}"

    def press(self) -> None:
        """Power the relay."""
        self.entity_description.press_action(self._doorstation.device, self._relay)
