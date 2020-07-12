"""Support for RFXtrx lights."""
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.const import ATTR_STATE, CONF_DEVICES, CONF_NAME, STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    ATTR_FIRE_EVENT,
    CONF_AUTOMATIC_ADD,
    CONF_FIRE_EVENT,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    SIGNAL_EVENT,
    RfxtrxDevice,
    fire_command_event,
    get_device_id,
    get_rfx_object,
)
from .const import COMMAND_OFF_LIST, COMMAND_ON_LIST

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DEVICES, default={}): {
            cv.string: vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Optional(CONF_FIRE_EVENT, default=False): cv.boolean,
                }
            )
        },
        vol.Optional(CONF_AUTOMATIC_ADD, default=False): cv.boolean,
        vol.Optional(
            CONF_SIGNAL_REPETITIONS, default=DEFAULT_SIGNAL_REPETITIONS
        ): vol.Coerce(int),
    }
)

SUPPORT_RFXTRX = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RFXtrx platform."""
    device_ids = set()

    # Add switch from config file
    entities = []
    for packet_id, entity_info in config[CONF_DEVICES].items():
        event = get_rfx_object(packet_id)
        if event is None:
            _LOGGER.error("Invalid device: %s", packet_id)
            continue

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            continue
        device_ids.add(device_id)

        datas = {ATTR_STATE: None, ATTR_FIRE_EVENT: entity_info[CONF_FIRE_EVENT]}
        entity = RfxtrxLight(
            entity_info[CONF_NAME], event.device, datas, config[CONF_SIGNAL_REPETITIONS]
        )

        entities.append(entity)

    add_entities(entities)

    def light_update(event):
        """Handle light updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or not event.device.known_to_be_dimmable
        ):
            return

        device_id = get_device_id(event.device)
        if device_id in device_ids:
            return
        device_ids.add(device_id)

        _LOGGER.debug(
            "Added light (Device ID: %s Class: %s Sub: %s)",
            event.device.id_string.lower(),
            event.device.__class__.__name__,
            event.device.subtype,
        )

        pkt_id = "".join(f"{x:02x}" for x in event.data)
        datas = {ATTR_STATE: None, ATTR_FIRE_EVENT: False}
        entity = RfxtrxLight(
            pkt_id, event.device, datas, DEFAULT_SIGNAL_REPETITIONS, event=event
        )

        add_entities([entity])

    # Subscribe to main RFXtrx events
    if config[CONF_AUTOMATIC_ADD]:
        hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, light_update)


class RfxtrxLight(RfxtrxDevice, LightEntity, RestoreEntity):
    """Representation of a RFXtrx light."""

    _brightness = 0

    async def async_added_to_hass(self):
        """Restore RFXtrx device state (ON/OFF)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_ON

        # Restore the brightness of dimmable devices
        if (
            old_state is not None
            and old_state.attributes.get(ATTR_BRIGHTNESS) is not None
        ):
            self._brightness = int(old_state.attributes[ATTR_BRIGHTNESS])

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, self._handle_event
            )
        )

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_RFXTRX

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            self._brightness = 255
            self._send_command("turn_on")
        else:
            self._brightness = brightness
            _brightness = brightness * 100 // 255
            self._send_command("dim", _brightness)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._brightness = 0
        self._send_command("turn_off")

    def _apply_event(self, event):
        """Apply command from rfxtrx."""
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False
        elif event.values["Command"] == "Set level":
            self._brightness = event.values["Dim level"] * 255 // 100
            self._state = self._brightness > 0

    def _handle_event(self, event):
        """Check if event applies to me and update."""
        if event.device.id_string != self._device.id_string:
            return

        self._apply_event(event)

        self.schedule_update_ha_state()
        if self.should_fire_event:
            fire_command_event(self.hass, self.entity_id, event.values["Command"])
