"""Support for RFXtrx covers."""
import logging

from homeassistant.components.cover import (
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.const import CONF_DEVICES, STATE_OPEN
from homeassistant.core import callback

from . import (
    DEFAULT_SIGNAL_REPETITIONS,
    RfxtrxCommandEntity,
    connect_auto_add,
    get_device_id,
    get_rfx_object,
)
from .const import (
    COMMAND_OFF_LIST,
    COMMAND_ON_LIST,
    CONF_DATA_BITS,
    CONF_SIGNAL_REPETITIONS,
    CONF_VENETIAN_BLIND_MODE,
    CONST_VENETIAN_BLIND_MODE_EU,
    CONST_VENETIAN_BLIND_MODE_US,
)

_LOGGER = logging.getLogger(__name__)


def supported(event):
    """Return whether an event supports cover."""
    return event.device.known_to_be_rollershutter


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up config entry."""
    discovery_info = config_entry.data
    device_ids = set()

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
            event.device,
            device_id,
            signal_repetitions=entity_info[CONF_SIGNAL_REPETITIONS],
            venetian_blind_mode=entity_info.get(CONF_VENETIAN_BLIND_MODE),
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
    connect_auto_add(hass, discovery_info, cover_update)


class RfxtrxCover(RfxtrxCommandEntity, CoverEntity):
    """Representation of a RFXtrx cover."""

    def __init__(
        self,
        device,
        device_id,
        signal_repetitions,
        event=None,
        venetian_blind_mode=None,
    ):
        """Initialize the RFXtrx cover device."""
        super().__init__(device, device_id, signal_repetitions, event)
        self._venetian_blind_mode = venetian_blind_mode

    async def async_added_to_hass(self):
        """Restore device state."""
        await super().async_added_to_hass()

        if self._event is None:
            old_state = await self.async_get_last_state()
            if old_state is not None:
                self._state = old_state.state == STATE_OPEN

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP

        if self._venetian_blind_mode in (
            CONST_VENETIAN_BLIND_MODE_US,
            CONST_VENETIAN_BLIND_MODE_EU,
        ):
            supported_features |= (
                SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_STOP_TILT
            )

        return supported_features

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return not self._state

    async def async_open_cover(self, **kwargs):
        """Move the cover up."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_up05sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_up2sec)
        else:
            await self._async_send(self._device.send_open)
        self._state = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs):
        """Move the cover down."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_down05sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_down2sec)
        else:
            await self._async_send(self._device.send_close)
        self._state = False
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._async_send(self._device.send_stop)
        self._state = True
        self.async_write_ha_state()

    async def async_open_cover_tilt(self, **kwargs):
        """Tilt the cover up."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_up2sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_up05sec)

    async def async_close_cover_tilt(self, **kwargs):
        """Tilt the cover down."""
        if self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_US:
            await self._async_send(self._device.send_down2sec)
        elif self._venetian_blind_mode == CONST_VENETIAN_BLIND_MODE_EU:
            await self._async_send(self._device.send_down05sec)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the cover tilt."""
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
