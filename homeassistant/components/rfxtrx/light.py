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
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.restore_state import RestoreEntity

from . import (
    CONF_AUTOMATIC_ADD,
    CONF_DEVICES,
    CONF_FIRE_EVENT,
    CONF_SIGNAL_REPETITIONS,
    DEFAULT_SIGNAL_REPETITIONS,
    SIGNAL_EVENT,
    RfxtrxDevice,
    fire_command_event,
    get_devices_from_config,
    get_new_device,
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
    lights = get_devices_from_config(config, RfxtrxLight)
    add_entities(lights)

    def light_update(event):
        """Handle light updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or not event.device.known_to_be_dimmable
        ):
            return

        new_device = get_new_device(event, config, RfxtrxLight)
        if new_device:
            new_device.apply_event(event)
            add_entities([new_device])

    # Subscribe to main RFXtrx events
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

        def _handle_event(event):
            """Check if event applies to me and update."""
            if event.device.id_string != self._event.device.id_string:
                return

            self.apply_event(event)

        self.async_on_remove(
            self.hass.helpers.dispatcher.async_dispatcher_connect(
                SIGNAL_EVENT, _handle_event
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

    def apply_event(self, event):
        """Apply command from rfxtrx."""
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False
        elif event.values["Command"] == "Set level":
            self._brightness = event.values["Dim level"] * 255 // 100
            self._state = self._brightness > 0

        if self.hass:
            self.schedule_update_ha_state()
            if self.should_fire_event:
                fire_command_event(self.hass, self.entity_id, event.values["Command"])
