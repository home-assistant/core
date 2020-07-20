"""Support for RFXtrx switches."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_DEVICES
from homeassistant.core import callback

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    DOMAIN,
    SIGNAL_EVENT,
    RfxtrxCommandEntity,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST, DATA_RFXTRX_CONFIG

DATA_SWITCH = f"{DOMAIN}_switch"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up config entry."""
    discovery_info = hass.data[DATA_RFXTRX_CONFIG]
    device_ids = set()

    def supported(event):
        return (
            isinstance(event.device, rfxtrxmod.LightingDevice)
            and not event.device.known_to_be_dimmable
            and not event.device.known_to_be_rollershutter
        )

    # Add switch from config file
    entities = []
    for packet_id, entity_info in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entity = RfxtrxSwitch(
            event.device, device_id, entity_info[CONF_SIGNAL_REPETITIONS]
        )
        entities.append(entity)

    async_add_entities(entities)

    @callback
    def switch_update(event, device_id):
        """Handle sensor updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added switch (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        entity = RfxtrxSwitch(
            event.device, device_id, DEFAULT_SIGNAL_REPETITIONS, event=event
        )
        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    if discovery_info[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, switch_update)


class RfxtrxSwitch(RfxtrxCommandEntity, SwitchEntity):
    """Representation of a RFXtrx switch."""

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        super()._apply_event(event)
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

    @callback
    def _handle_event(self, event, device_id):
        """Check if event applies to me and update."""
        if device_id != self._device_id:
            return

        self._apply_event(event)

        self.async_write_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")
        self.schedule_update_ha_state()
