"""Support for pico and keypad button events."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LutronCasetaDevice
from .const import ACTION_PRESS, ACTION_RELEASE, DOMAIN
from .models import (
    LutronCasetaButtonDevice,
    LutronCasetaButtonEventData,
    LutronCasetaConfigEntry,
    LutronCasetaData,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LutronCasetaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Lutron pico and keypad buttons."""
    data = config_entry.runtime_data
    async_add_entities(
        LutronCasetaButtonEvent(data, button_device, config_entry.entry_id)
        for button_device in data.button_devices
    )


class LutronCasetaButtonEvent(LutronCasetaDevice, EventEntity):
    """Representation of a Lutron pico and keypad button event."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [ACTION_PRESS, ACTION_RELEASE]
    _attr_has_entity_name = True

    def __init__(
        self,
        data: LutronCasetaData,
        button_device: LutronCasetaButtonDevice,
        entry_id: str,
    ) -> None:
        """Init a button event entity."""
        super().__init__(button_device.device, data)
        self._attr_name = button_device.button_name
        self._attr_translation_key = button_device.button_key
        self._attr_device_info = button_device.parent_device_info
        self._button_id = button_device.button_id
        self._entry_id = entry_id

    @property
    def serial(self):
        """Buttons shouldn't have serial numbers, Return None."""
        return None

    @callback
    def _async_handle_button_event(self, data: LutronCasetaButtonEventData) -> None:
        """Handle a button event."""
        self._trigger_event(data["action"])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to button events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry_id}_button_{self._button_id}",
                self._async_handle_button_event,
            )
        )
        await super().async_added_to_hass()
