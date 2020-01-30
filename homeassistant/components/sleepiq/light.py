"""
Support for switching lights on Sleep Number beds off and on.

Creates entities for both night stand lamps and the two
night light (underbed) lights. Night lights cannot be
controlled separately by the stock remote but can be with
this integration.
"""

import logging

from homeassistant.components import sleepiq

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:lamp"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the SleepIQ lights."""
    if discovery_info is None:
        return

    data = sleepiq.DATA
    data.update()

    dev = list()

    for bed_id, bed in data.beds.items():  # pylint: disable=unused-variable
        for light in sleepiq.BED_LIGHTS:
            dev.append(SleepNumberLight(data, bed_id, light))
    add_entities(dev)


class SleepNumberLight(sleepiq.SleepIQLight):
    """Representation of a SleepIQ Light."""

    def __init__(self, sleepiq_data, bed_id, light):
        """Initialize the light."""
        sleepiq.SleepIQLight.__init__(self, sleepiq_data, bed_id, light)

        self._light = light
        self._state = False
        self.type = sleepiq.SLEEP_NUMBER
        self._bed_id = bed_id

    @property
    def state(self):
        """Return state of light."""
        return "on" if self._state else "off"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    async def async_turn_on(self):
        """Instruct the light to turn on."""
        self.turn_on()

    async def async_turn_off(self):
        """Instruct the light to turn off."""
        self.turn_off()

    def update(self):
        """Get the latest data from SleepIQ and updates the states."""
        sleepiq.SleepIQLight.update(self)
        self._state = self.is_on
