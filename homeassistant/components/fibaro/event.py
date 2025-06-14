"""Support for Fibaro event entities."""

from __future__ import annotations

from pyfibaro.fibaro_device import DeviceModel, SceneEvent
from pyfibaro.fibaro_state_resolver import FibaroEvent

from homeassistant.components.event import (
    ENTITY_ID_FORMAT,
    EventDeviceClass,
    EventEntity,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FibaroConfigEntry
from .entity import FibaroEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FibaroConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fibaro event entities."""
    controller = entry.runtime_data

    # Each scene event represents a button on a device
    async_add_entities(
        (
            FibaroEventEntity(device, scene_event)
            for device in controller.fibaro_devices[Platform.EVENT]
            for scene_event in device.central_scene_event
        ),
        True,
    )


class FibaroEventEntity(FibaroEntity, EventEntity):
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
        self.async_on_remove(
            self.controller.register_event(
                self.fibaro_device.fibaro_id, self._event_callback
            )
        )

    def _event_callback(self, event: FibaroEvent) -> None:
        if (
            event.event_type.lower() == "centralsceneevent"
            and event.key_id == self._button
        ):
            self._trigger_event(event.key_event_type)
            self.schedule_update_ha_state()
