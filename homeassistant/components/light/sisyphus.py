"""
Exposes a Sisyphus Kinetic Art Table as a light.

Turning the switch off will sleep the table; turning it on will wake it up.
Brightness controls the table light brightness.
"""
import logging

from homeassistant.const import CONF_NAME
from homeassistant.components.light import SUPPORT_BRIGHTNESS, Light
from homeassistant.components.sisyphus import DATA_SISYPHUS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['sisyphus']


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
        self._initialized = False

    def update(self):
        """Lazily initializes the table."""
        if not self._initialized:
            # We wait until update before adding the listener because
            # otherwise there's a race condition by which this entity
            # might not have had its hass field set, and thus
            # the schedule_update_ha_state call will fail
            self._table.add_listener(
                lambda: self.schedule_update_ha_state(False))
            self._initialized = True

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
        """Return the urrent brightness of the table's ring light."""
        return self._table.brightness * 255

    @property
    def supported_features(self):
        """Return the eatures supported by the table; i.e. brightness."""
        return SUPPORT_BRIGHTNESS

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
