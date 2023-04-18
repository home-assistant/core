from __future__ import annotations
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import RingEntityMixin



async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    entities = [
        description.cls(config_entry.entry_id, device, description)
        for device_type in ("doorbots", "other")
        for description in BUTTON_TYPES
        if device_type in description.category
        for device in devices[device_type]
    ]

    async_add_entities(entities)

@dataclass
class RingRequiredKeysMixin:
    category: list[str]
    cls: type[RingButton]

@dataclass
class RingButtonEntityDescription(ButtonEntityDescription, RingRequiredKeysMixin):
    kind: str | None = None

class RingDoorButton(RingEntityMixin, ButtonEntity):
    entity_description: RingButtonEntityDescription

    def __init__(
        self,
        config_entry_id,
        device,
        description: RingButtonEntityDescription,
    ) -> None:
        super().__init__(config_entry_id, device)
        self.entity_description = description
        self._extra = None
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{device.id}-{description.key}"

    def press(self) -> None:
        self._device.open_door()

BUTTON_TYPES: tuple[RingButtonEntityDescription, ...] = (
    RingButtonEntityDescription(
        key="open_door",
        name="Open door",
        category=["other"],
        icon="mdi:door-closed-lock",
        cls=RingDoorButton,
    ),
)
