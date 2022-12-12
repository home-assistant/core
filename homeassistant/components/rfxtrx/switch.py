"""Support for RFXtrx switches."""
from __future__ import annotations

import logging
from typing import Any

import RFXtrx as rfxtrxmod

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COMMAND_OFF, CONF_COMMAND_ON, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    DOMAIN,
    DeviceTuple,
    RfxtrxCommandEntity,
    async_setup_platform_entry,
    get_pt2262_cmd,
)
from .const import (
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    CONF_DATA_BITS,
    DEVICE_PACKET_TYPE_LIGHTING4,
)

DATA_SWITCH = f"{DOMAIN}_switch"

_LOGGER = logging.getLogger(__name__)


def supported(event: rfxtrxmod.RFXtrxEvent) -> bool:
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
        entity_info: dict[str, Any],
    ) -> list[Entity]:
        return [
            RfxtrxSwitch(
                event.device,
                device_id,
                entity_info.get(CONF_DATA_BITS),
                entity_info.get(CONF_COMMAND_ON),
                entity_info.get(CONF_COMMAND_OFF),
                event=event if auto else None,
            )
        ]

    await async_setup_platform_entry(
        hass, config_entry, async_add_entities, supported, _constructor
    )


class RfxtrxSwitch(RfxtrxCommandEntity, SwitchEntity):
    """Representation of a RFXtrx switch."""

    def __init__(
        self,
        device: rfxtrxmod.RFXtrxDevice,
        device_id: DeviceTuple,
        data_bits: int | None = None,
        cmd_on: int | None = None,
        cmd_off: int | None = None,
        event: rfxtrxmod.RFXtrxEvent | None = None,
    ) -> None:
        """Initialize the RFXtrx switch."""
        super().__init__(device, device_id, event=event)
        self._data_bits = data_bits
        self._cmd_on = cmd_on
        self._cmd_off = cmd_off

    async def async_added_to_hass(self) -> None:
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._attr_is_on = old_state.state == STATE_ON

    def _apply_event_lighting4(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply event for a lighting 4 device."""
        if self._data_bits is not None:
            cmdstr = get_pt2262_cmd(event.device.id_string, self._data_bits)
            assert cmdstr
            cmd = int(cmdstr, 16)
            if cmd == self._cmd_on:
                self._attr_is_on = True
            elif cmd == self._cmd_off:
                self._attr_is_on = False
        else:
            self._attr_is_on = True

    def _apply_event_standard(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        assert isinstance(event, rfxtrxmod.ControlEvent)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._attr_is_on = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._attr_is_on = False

    def _apply_event(self, event: rfxtrxmod.RFXtrxEvent) -> None:
        """Apply command from rfxtrx."""
        super()._apply_event(event)
        if event.device.packettype == DEVICE_PACKET_TYPE_LIGHTING4:
            self._apply_event_lighting4(event)
        else:
            self._apply_event_standard(event)

    @callback
    def _handle_event(
        self, event: rfxtrxmod.RFXtrxEvent, device_id: DeviceTuple
    ) -> None:
        """Check if event applies to me and update."""
        if self._event_applies(event, device_id):
            self._apply_event(event)

            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        if self._cmd_on is not None:
            await self._async_send(self._device.send_command, self._cmd_on)
        else:
            await self._async_send(self._device.send_on)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        if self._cmd_off is not None:
            await self._async_send(self._device.send_command, self._cmd_off)
        else:
            await self._async_send(self._device.send_off)
        self._attr_is_on = False
        self.async_write_ha_state()
