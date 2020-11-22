"""Support for RFXtrx lights."""
import logging

import RFXtrx as rfxtrxmod

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import CONF_DEVICES, STATE_ON
from homeassistant.core import callback

from . import (
    CONF_DATA_BITS,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    RfxtrxCommandEntity,
    connect_auto_add,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

_LOGGER = logging.getLogger(__name__)

SUPPORT_RFXTRX = SUPPORT_BRIGHTNESS


def supported(event):
    """Return whether an event supports light."""
    return (
        isinstance(event.device, rfxtrxmod.LightingDevice)
        and event.device.known_to_be_dimmable
    )


async def async_setup_entry(
    hass,
    config_entry,
    async_add_entities,
):
    """Set up config entry."""
    discovery_info = config_entry.data
    device_ids = set()

    # Add switch from config file
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

        entity = RfxtrxLight(
            event.device, device_id, entity_info[CONF_SIGNAL_REPETITIONS]
        )

        entities.append(entity)

    async_add_entities(entities)

    @callback
    def light_update(event, device_id):
        """Handle light updates from the RFXtrx gateway."""
        if not supported(event):
            return

        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.info(
            "Added light (Device ID: %s Class: %s Sub: %s, Event: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
            "".join(f"{x:02x}" for x in event.data),
        )

        entity = RfxtrxLight(
            event.device, device_id, DEFAULT_SIGNAL_REPETITIONS, event=event
        )

        async_add_entities([entity])

    # Subscribe to main RFXtrx events
    connect_auto_add(hass, discovery_info, light_update)


class RfxtrxLight(RfxtrxCommandEntity, LightEntity):
    """Representation of a RFXtrx light."""

    _brightness = 0

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
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_RFXTRX

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

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
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
