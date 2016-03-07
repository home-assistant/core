"""
Support for SCSGate lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.scsgate/
"""
import logging

import homeassistant.components.scsgate as scsgate
from homeassistant.components.light import Light
from homeassistant.const import ATTR_ENTITY_ID

DEPENDENCIES = ['scsgate']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add the SCSGate swiches defined inside of the configuration file."""
    devices = config.get('devices')
    lights = []
    logger = logging.getLogger(__name__)

    if devices:
        for _, entity_info in devices.items():
            if entity_info['scs_id'] in scsgate.SCSGATE.devices:
                continue

            logger.info("Adding %s scsgate.light", entity_info['name'])

            name = entity_info['name']
            scs_id = entity_info['scs_id']
            light = SCSGateLight(
                name=name,
                scs_id=scs_id,
                logger=logger)
            lights.append(light)

    add_devices_callback(lights)
    scsgate.SCSGATE.add_devices_to_register(lights)


class SCSGateLight(Light):
    """representation of a SCSGate light."""

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
            ToggleStatusTask(
                target=self._scs_id,
                toggled=True))

        self._toggled = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        from scsgate.tasks import ToggleStatusTask

        scsgate.SCSGATE.append_task(
            ToggleStatusTask(
                target=self._scs_id,
                toggled=False))

        self._toggled = False
        self.update_ha_state()

    def process_event(self, message):
        """Handle a SCSGate message related with this light."""
        if self._toggled == message.toggled:
            self._logger.info(
                "Light %s, ignoring message %s because state already active",
                self._scs_id, message)
            # Nothing changed, ignoring
            return

        self._toggled = message.toggled
        self.update_ha_state()

        command = "off"
        if self._toggled:
            command = "on"

        self.hass.bus.fire(
            'button_pressed', {
                ATTR_ENTITY_ID: self._scs_id,
                'state': command
            }
        )
