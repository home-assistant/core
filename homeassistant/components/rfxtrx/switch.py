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
    RECEIVED_EVT_SUBSCRIBERS,
    RfxtrxDevice,
    apply_received_command,
    get_devices_from_config,
    get_new_device,
)

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
            add_entities_callback([new_device])

        apply_received_command(event)

    # Subscribe to main RFXtrx events
    if switch_update not in RECEIVED_EVT_SUBSCRIBERS:
        RECEIVED_EVT_SUBSCRIBERS.append(switch_update)


class RfxtrxSwitch(RfxtrxDevice, SwitchEntity, RestoreEntity):
    """Representation of a RFXtrx switch."""

    async def async_added_to_hass(self):
        """Restore RFXtrx switch device state (ON/OFF)."""
        await super().async_added_to_hass()

        old_state = await self.async_get_last_state()
        if old_state is not None:
            self._state = old_state.state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._send_command("turn_on")
