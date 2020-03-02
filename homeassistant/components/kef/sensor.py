"""KEF sensors."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from .const import DOMAIN, SLIDERS

_LOGGER = logging.getLogger(__name__)

_LOGGER.debug("Imported sensor.py")


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEF sensors."""
    _LOGGER.debug("Setting up sensors")
    sensors = []
    for media_player in hass.data[DOMAIN].values():
        for var, unit in SLIDERS:
            sensors.append(KEFSensor(media_player, var, unit,))

    async_add_entities(sensors)


class KEFSensor(Entity):
    """Representation of a KEF sensor."""

    def __init__(self, media_player, var, unit):
        """Initialize a KEF DSP sensor."""
        self._name = f"{media_player.name}_{var}"
        _LOGGER.debug(f"Setting up {self._name}")
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, self._name, hass=media_player.hass
        )
        self._media_player = media_player
        self._var = var
        self._value = None
        self._unit = unit

    @property
    def name(self):
        """Return the friendly name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._media_player.name}-{self._var}"

    @property
    def state(self):
        """Return the state of the device."""
        return self._value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def should_poll(self):
        """Return False because entity pushes its state."""
        return False
