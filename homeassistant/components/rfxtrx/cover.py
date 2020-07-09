"""Support for RFXtrx covers."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.cover import CoverEntity
from homeassistant.const import CONF_COVERS, STATE_OPEN
from homeassistant.core import callback
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    SIGNAL_EVENT,
    RfxtrxDevice,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up config entry."""
    config = config_entry.data[CONF_COVERS]
    device_ids = set()

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

        entity = RfxtrxCover(event.device, entity_info[CONF_SIGNAL_REPETITIONS])
        entities.append(entity)

    async_add_entities(entities)

    @callback
    def cover_update(event):
        """Handle cover updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or event.device.known_to_be_dimmable
            or not event.device.known_to_be_rollershutter
        ):
            return

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added cover (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
        )

        entity = RfxtrxCover(event.device, DEFAULT_SIGNAL_REPETITIONS, event=event)
        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, cover_update)


class RfxtrxCover(RfxtrxDevice, CoverEntity, RestoreEntity):
    """Representation of a RFXtrx cover."""

    async def async_added_to_hass(self):
        """Restore RFXtrx cover device state (OPEN/CLOSE)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_OPEN

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
            )
        )

    @property
    def should_poll(self):
        """Return the polling state. No polling available in RFXtrx cover."""
        return False

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._state

    def open_cover(self, **kwargs):
        """Move the cover up."""
        self._send_command("roll_up")

    def close_cover(self, **kwargs):
        """Move the cover down."""
        self._send_command("roll_down")

    def stop_cover(self, **kwargs):
        """Stop the cover."""
        self._send_command("stop_roll")

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
