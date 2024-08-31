"""Support for Fibaro event entities."""
from __future__ import annotations

from pyfibaro.fibaro_device import DeviceModel, SceneEvent
from pyfibaro.fibaro_state_resolver import FibaroEvent

from homeassistant.components.event import (
    ENTITY_ID_FORMAT,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FibaroController, FibaroDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro event entities."""
    controller: FibaroController = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for device in controller.fibaro_devices[Platform.EVENT]:
        for scene_event in device.central_scene_event:
            # Each scene event represents a button on a device
            entities.append(FibaroEventEntity(device, scene_event))

    async_add_entities(entities, True)


class FibaroEventEntity(FibaroDevice, EventEntity):
    """Representation of a Fibaro Event Entity."""

    def __init__(self, fibaro_device: DeviceModel, scene_event: SceneEvent) -> None:
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)

        key_id = scene_event.key_id

        self.entity_id = ENTITY_ID_FORMAT.format(f"{self.ha_id}_button_{key_id}")

        self._button = key_id

        self._attr_name = f"{fibaro_device.friendly_name} Button {key_id}"
        self._attr_device_class = EventDeviceClass.BUTTON
        self._attr_event_types = scene_event.key_event_types
        self._attr_unique_id = f"{fibaro_device.unique_id_str}.{key_id}"

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()

        # Register event callback
        self.controller.register_event(
            self.fibaro_device.fibaro_id, self._event_callback
        )

    def _event_callback(self, event: FibaroEvent) -> None:
        if event.key_id == self._button:
            self._trigger_event(event.key_event_type)
            self.schedule_update_ha_state()
