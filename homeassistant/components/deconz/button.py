"""Support for deCONZ buttons."""

from __future__ import annotations

from collections.abc import ValuesView
from dataclasses import dataclass

from pydeconz.group import Scene as PydeconzScene

from homeassistant.components.button import (
    DOMAIN,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
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
    def async_add_scene(
        scenes: list[PydeconzScene]
        | ValuesView[PydeconzScene] = gateway.api.scenes.values(),
    ) -> None:
        """Add scene button from deCONZ."""
        entities = []

        for scene in scenes:

            known_entities = set(gateway.entities[DOMAIN])
            for description in ENTITY_DESCRIPTIONS.get(PydeconzScene, []):

                new_entity = DeconzButton(scene, gateway, description)
                if new_entity.unique_id not in known_entities:
                    entities.append(new_entity)

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            gateway.signal_new_scene,
            async_add_scene,
        )
    )

    async_add_scene()


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
