"""Support for RFXtrx switches."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_SWITCHES, STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    DOMAIN,
    SIGNAL_EVENT,
    RfxtrxDevice,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

DATA_SWITCH = f"{DOMAIN}_switch"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up config entry."""
    config = config_entry.data[CONF_SWITCHES]
    device_ids = set()

    # Add switch from config file
    entities = []
    for packet_id, entity_info in config.items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entities.append(
            RfxtrxSwitch(event.device, entity_info[CONF_SIGNAL_REPETITIONS])
        )
    async_add_entities(entities)

    @callback
    def switch_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or event.device.known_to_be_dimmable
            or event.device.known_to_be_rollershutter
        ):
            return

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added switch (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
        )

        entity = RfxtrxSwitch(event.device, DEFAULT_SIGNAL_REPETITIONS, event=event)
        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, switch_update)


class RfxtrxSwitch(RfxtrxDevice, SwitchEntity, RestoreEntity):
    """Representation of a RFXtrx switch."""

    async def async_added_to_hass(self):
        """Restore RFXtrx switch device state (ON/OFF)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_ON

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
            )
        )

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    @callback
    def _handle_event(self, event):
        """Check if event applies to me and update."""
        if event.device.id_string != self._device.id_string:
            return

        self._apply_event(event)

        self.async_write_ha_state()

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")
        self.schedule_update_ha_state()
