"""Support for RFXtrx lights."""
from __future__ import annotations

import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DeviceTuple, RfxtrxCommandEntity, async_setup_platform_entry
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

_LOGGER = logging.getLogger(__name__)


def supported(event: rfxtrxmod.RFXtrxEvent):
    """Return whether an event supports light."""
    return (
        isinstance(event.device, rfxtrxmod.LightingDevice)
        and event.device.known_to_be_dimmable
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up config entry."""

    def _constructor(
        event: rfxtrxmod.RFXtrxEvent,
        auto: rfxtrxmod.RFXtrxEvent | None,
        device_id: DeviceTuple,
        entity_info: dict,
    ):
        return [
            RfxtrxLight(
                event.device,
                device_id,
                event=event if auto else None,
            )
        ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxLight(RfxtrxCommandEntity, LightEntity):
    """Representation of a RFXtrx light."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _brightness = 0
    _device: rfxtrxmod.LightingDevice

    async def async_added_to_hass(self):
        """Restore RFXtrx device state (ON/OFF)."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._state = old_state.state == STATE_ON
                self._brightness = old_state.attributes.get(ATTR_BRIGHTNESS)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        self._state = True
        if brightness is None:
            await self._async_send(self._device.send_on)
            self._brightness = 255
        else:
            await self._async_send(self._device.send_dim, brightness * 100 // 255)
            self._brightness = brightness

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._async_send(self._device.send_off)
        self._state = False
        self._brightness = 0
        self.async_write_ha_state()

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent):
        """Apply command from rfxtrx."""
        assert isinstance(event, rfxtrxmod.ControlEvent)
        super()._apply_event(event)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False
        elif event.values["Command"] == "Set level":
            self._brightness = event.values["Dim level"] * 255 // 100
            self._state = self._brightness > 0

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        self._apply_event(event)

        self.async_write_ha_state()
