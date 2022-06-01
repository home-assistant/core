"""Support for deCONZ buttons."""

from __future__ import annotations

from dataclasses import dataclass

from pydeconz.models.event import EventType
from pydeconz.models.scene import Scene as PydeconzScene

from homeassistant.components.button import (
    DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzSceneMixin
from .gateway import DeconzGateway, get_gateway_from_config_entry


@dataclass
class DeconzButtonDescriptionMixin:
    """Required values when describing deCONZ button entities."""

    suffix: str
    button_fn: str


@dataclass
class DeconzButtonDescription(ButtonEntityDescription, DeconzButtonDescriptionMixin):
    """Class describing deCONZ button entities."""


ENTITY_DESCRIPTIONS = {
    PydeconzScene: [
        DeconzButtonDescription(
            key="store",
            button_fn="store",
            suffix="Store Current Scene",
            icon="mdi:inbox-arrow-down",
            entity_category=EntityCategory.CONFIG,
        )
    ]
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the deCONZ button entity."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_scene(_: EventType, scene_id: str) -> None:
        """Add scene button from deCONZ."""
        scene = gateway.api.scenes[scene_id]
        async_add_entities(
            DeconzButton(scene, gateway, description)
            for description in ENTITY_DESCRIPTIONS.get(PydeconzScene, [])
        )

    gateway.register_platform_add_device_callback(
        async_add_scene,
        gateway.api.scenes,
    )


class DeconzButton(DeconzSceneMixin, ButtonEntity):
    """Representation of a deCONZ button entity."""

    TYPE = DOMAIN

    def __init__(
        self,
        device: PydeconzScene,
        gateway: DeconzGateway,
        description: DeconzButtonDescription,
    ) -> None:
        """Initialize deCONZ number entity."""
        self.entity_description: DeconzButtonDescription = description
        super().__init__(device, gateway)

        self._attr_name = f"{self._attr_name} {description.suffix}"

    async def async_press(self) -> None:
        """Store light states into scene."""
        async_button_fn = getattr(self._device, self.entity_description.button_fn)
        await async_button_fn()

    def get_device_identifier(self) -> str:
        """Return a unique identifier for this scene."""
        return f"{super().get_device_identifier()}-{self.entity_description.key}"
