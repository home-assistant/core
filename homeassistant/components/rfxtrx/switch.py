"""Support for RFXtrx switches."""
import logging

import RFXtrx as rfxtrxmod
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
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


def setup_platform(hass, config, add_entities_callback, discovery_info=None):
    """Set up the RFXtrx platform."""
    # Add switch from config file
    switches = get_devices_from_config(config, RfxtrxSwitch)
    add_entities_callback(switches)

    def switch_update(event):
        """Handle sensor updates from the RFXtrx gateway."""
        if (
            not isinstance(event.device, rfxtrxmod.LightingDevice)
            or event.device.known_to_be_dimmable
            or event.device.known_to_be_rollershutter
        ):
            return

        new_device = get_new_device(event, config, RfxtrxSwitch)
        if new_device:
            new_device.apply_event(event)
            add_entities_callback([new_device])

    # Subscribe to main RFXtrx events
    hass.helpers.dispatcher.dispatcher_connect(SIGNAL_EVENT, switch_update)


class RfxtrxSwitch(RfxtrxDevice, SwitchEntity, RestoreEntity):
    """Representation of a RFXtrx switch."""

    async def async_added_to_hass(self):
        """Restore RFXtrx switch device state (ON/OFF)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_ON

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

    def apply_event(self, event):
        """Apply command from rfxtrx."""
        if event.values["Command"] in COMMAND_ON_LIST:
            self._state = True
        elif event.values["Command"] in COMMAND_OFF_LIST:
            self._state = False

        if self.hass:
            self.schedule_update_ha_state()
            if self.should_fire_event:
                fire_command_event(self.hass, self.entity_id, event.values["Command"])

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._send_command("turn_off")
