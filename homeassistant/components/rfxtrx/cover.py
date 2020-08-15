"""Support for RFXtrx covers."""
import logging

from homeassistant.components.cover import CoverEntity
from homeassistant.const import CONF_DEVICES, STATE_OPEN
from homeassistant.core import callback

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DATA_BITS,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    SIGNAL_EVENT,
    RfxtrxCommandEntity,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass, config_entry, async_add_entities,
):
    """Set up config entry."""
    discovery_info = config_entry.data
    device_ids = set()

    def supported(event):
        return event.device.known_to_be_rollershutter

    entities = []
    for packet_id, entity_info in discovery_info[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue
        if not supported(event):
            continue

        device_id = get_device_id(
            event.device, data_bits=entity_info.get(CONF_DATA_BITS)
        )
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        entity = RfxtrxCover(
            event.device, device_id, entity_info[CONF_SIGNAL_REPETITIONS]
        )
        entities.append(entity)

    async_add_entities(entities)

    @callback
    def cover_update(event, device_id):
        """Handle cover updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added cover (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        entity = RfxtrxCover(
            event.device, device_id, DEFAULT_SIGNAL_REPETITIONS, event=event
        )
        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    if discovery_info[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.async_dispatcher_connect(SIGNAL_EVENT, cover_update)


class RfxtrxCover(RfxtrxCommandEntity, CoverEntity):
    """Representation of a RFXtrx cover."""

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._state = old_state.state == STATE_OPEN

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._state

    async def async_open_cover(self, **kwargs):
        """Move the cover up."""
        await self._async_send(self._device.send_open)
        self._state = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Move the cover down."""
        await self._async_send(self._device.send_close)
        self._state = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._async_send(self._device.send_stop)
        self._state = True
        self.async_write_ha_state()

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
