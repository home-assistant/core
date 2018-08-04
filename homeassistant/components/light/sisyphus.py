"""
Support for the light on the Sisyphus Kinetic Art Table.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.sisyphus/
"""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.components.sisyphus import DATA_SISYPHUS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['sisyphus']

SUPPORTED_FEATURES = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a single Sisyphus table."""
    name = discovery_info[CONF_NAME]
    add_devices(
        [SisyphusLight(name, hass.data[DATA_SISYPHUS][name])],
        update_before_add=True)


class SisyphusLight(Light):
    """Represents a Sisyphus table as a light."""

    def __init__(self, name, table):
        """
        Constructor.

        :param name: name of the table
        :param table: sisyphus-control Table object
        """
        self._name = name
        self._table = table

    async def async_added_to_hass(self):
        """Add listeners after this object has been initialized."""
        self._table.add_listener(
            lambda: self.async_schedule_update_ha_state(False))

    @property
    def name(self):
        """Return the ame of the table."""
        return self._name

    @property
    def is_on(self):
        """Return True if the table is on."""
        return not self._table.is_sleeping

    @property
    def brightness(self):
        """Return the current brightness of the table's ring light."""
        return self._table.brightness * 255

    @property
    def supported_features(self):
        """Return the features supported by the table; i.e. brightness."""
        return SUPPORTED_FEATURES

    async def async_turn_off(self, **kwargs):
        """Put the table to sleep."""
        await self._table.sleep()
        _LOGGER.debug("Sisyphus table %s: sleep")

    async def async_turn_on(self, **kwargs):
        """Wake up the table if necessary, optionally changes brightness."""
        if not self.is_on:
            await self._table.wakeup()
            _LOGGER.debug("Sisyphus table %s: wakeup")

        if "brightness" in kwargs:
            await self._table.set_brightness(kwargs["brightness"] / 255.0)
