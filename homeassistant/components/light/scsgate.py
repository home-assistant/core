"""
Support for SCSGate lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.scsgate/
"""
import logging

import voluptuous as vol

import homeassistant.components.scsgate as scsgate
from homeassistant.components.light import (Light, PLATFORM_SCHEMA)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_STATE, CONF_DEVICES, CONF_NAME)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['scsgate']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.Schema({cv.slug: scsgate.SCSGATE_SCHEMA}),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the SCSGate switches."""
    devices = config.get(CONF_DEVICES)
    lights = []
    logger = logging.getLogger(__name__)

    if devices:
        for _, entity_info in devices.items():
            if entity_info[scsgate.CONF_SCS_ID] in scsgate.SCSGATE.devices:
                continue

            name = entity_info[CONF_NAME]
            scs_id = entity_info[scsgate.CONF_SCS_ID]

            logger.info("Adding %s scsgate.light", name)

            light = SCSGateLight(name=name, scs_id=scs_id, logger=logger)
            lights.append(light)

    add_devices(lights)
    scsgate.SCSGATE.add_devices_to_register(lights)


class SCSGateLight(Light):
    """Representation of a SCSGate light."""

    def __init__(self, scs_id, name, logger):
        """Initialize the light."""
        self._name = name
        self._scs_id = scs_id
        self._toggled = False
        self._logger = logger

    @property
    def scs_id(self):
        """Return the SCS ID."""
        return self._scs_id

    @property
    def should_poll(self):
        """No polling needed for a SCSGate light."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._toggled

    def turn_on(self, **kwargs):
        """Turn the device on."""
        from scsgate.tasks import ToggleStatusTask

        scsgate.SCSGATE.append_task(
            ToggleStatusTask(target=self._scs_id, toggled=True))

        self._toggled = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        from scsgate.tasks import ToggleStatusTask

        scsgate.SCSGATE.append_task(
            ToggleStatusTask(target=self._scs_id, toggled=False))

        self._toggled = False
        self.schedule_update_ha_state()

    def process_event(self, message):
        """Handle a SCSGate message related with this light."""
        if self._toggled == message.toggled:
            self._logger.info(
                "Light %s, ignoring message %s because state already active",
                self._scs_id, message)
            # Nothing changed, ignoring
            return

        self._toggled = message.toggled
        self.schedule_update_ha_state()

        command = "off"
        if self._toggled:
            command = "on"

        self.hass.bus.fire(
            'button_pressed', {
                ATTR_ENTITY_ID: self._scs_id,
                ATTR_STATE: command,
            }
        )
