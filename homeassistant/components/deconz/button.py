"""Support for deCONZ buttons."""

from __future__ import annotations

from dataclasses import dataclass

from pydeconz.models.event import EventType
from pydeconz.models.scene import Scene as PydeconzScene
from pydeconz.models.sensor.presence import Presence

from homeassistant.components.button import (
    DOMAIN,
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .deconz_device import DeconzDevice, DeconzSceneMixin
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
            DeconzSceneButton(scene, gateway, description)
            for description in ENTITY_DESCRIPTIONS.get(PydeconzScene, [])
        )

    gateway.register_platform_add_device_callback(
        async_add_scene,
        gateway.api.scenes,
    )

    @callback
    def async_add_presence_sensor(_: EventType, sensor_id: str) -> None:
        """Add presence sensor reset button from deCONZ."""
        sensor = gateway.api.sensors.presence[sensor_id]
        if sensor.presence_event is not None:
            async_add_entities([DeconzPresenceResetButton(sensor, gateway)])

    gateway.register_platform_add_device_callback(
        async_add_presence_sensor,
        gateway.api.sensors.presence,
    )


class DeconzSceneButton(DeconzSceneMixin, ButtonEntity):
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
        async_button_fn = getattr(
            self.gateway.api.scenes,
            self.entity_description.button_fn,
        )
        await async_button_fn(self._device.group_id, self._device.id)

    def get_device_identifier(self) -> str:
        """Return a unique identifier for this scene."""
        return f"{super().get_device_identifier()}-{self.entity_description.key}"


class DeconzPresenceResetButton(DeconzDevice[Presence], ButtonEntity):
    """Representation of a deCONZ presence reset button entity."""

    _name_suffix = "Reset Presence"
    unique_id_suffix = "reset_presence"

    _attr_entity_category = EntityCategory.CONFIG
    _attr_device_class = ButtonDeviceClass.RESTART

    TYPE = DOMAIN

    async def async_press(self) -> None:
        """Store reset presence state."""
        await self.gateway.api.sensors.presence.set_config(
            id=self._device.resource_id,
            reset_presence=True,
        )
