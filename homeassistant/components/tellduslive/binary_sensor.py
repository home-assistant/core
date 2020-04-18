"""Support for binary sensors using Tellstick Net."""
import logging

from homeassistant.components import binary_sensor, tellduslive
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .entry import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""

    async def async_discover_binary_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveSensor(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(
            binary_sensor.DOMAIN, tellduslive.DOMAIN
        ),
        async_discover_binary_sensor,
    )


class TelldusLiveSensor(TelldusLiveEntity, BinarySensorDevice):
    """Representation of a Tellstick sensor."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.is_on
