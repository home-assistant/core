"""Support for RFXtrx switches."""
from __future__ import annotations

import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    DEFAULT_SIGNAL_REPETITIONS,
    DOMAIN,
    DeviceTuple,
    RfxtrxCommandEntity,
    async_setup_platform_entry,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST, CONF_SIGNAL_REPETITIONS

DATA_SWITCH = f"{DOMAIN}_switch"

_LOGGER = logging.getLogger(__name__)


def supported(event):
    """Return whether an event supports switch."""
    return (
        isinstance(event.device, rfxtrxmod.LightingDevice)
        and not event.device.known_to_be_dimmable
        and not event.device.known_to_be_rollershutter
        or isinstance(event.device, rfxtrxmod.RfyDevice)
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
            RfxtrxSwitch(
                event.device,
                device_id,
                entity_info.get(CONF_SIGNAL_REPETITIONS, DEFAULT_SIGNAL_REPETITIONS),
                event=event if auto else None,
            )
        ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxSwitch(RfxtrxCommandEntity, SwitchEntity):
    """Representation of a RFXtrx switch."""

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._state = old_state.state == STATE_ON

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply command from rfxtrx."""
        assert isinstance(event, rfxtrxmod.ControlEvent)
        super()._apply_event(event)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    @callback
    def _handle_event(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> None:
        """Check if event applies to me and update."""
        if self._event_applies(event, device_id):
            self._apply_event(event)

            self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._async_send(self._device.send_on)
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._async_send(self._device.send_off)
        self._state = False
        self.async_write_ha_state()
