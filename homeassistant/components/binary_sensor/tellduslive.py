"""
Support for binary sensors using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.tellduslive/

"""
import logging

from homeassistant.components import binary_sensor, tellduslive
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.tellduslive.entry import TelldusLiveEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tellstick sensors."""
    if discovery_info is None:
        return
    client = hass.data[tellduslive.DOMAIN]
    add_entities(
        TelldusLiveSensor(client, binary_sensor)
        for binary_sensor in discovery_info
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tellduslive sensors dynamically."""
    async def async_discover_binary_sensor(device_id):
        """Discover and add a discovered sensor."""
        client = hass.data[tellduslive.DOMAIN]
        async_add_entities([TelldusLiveSensor(client, device_id)])

    async_dispatcher_connect(
        hass,
        tellduslive.TELLDUS_DISCOVERY_NEW.format(binary_sensor.DOMAIN,
                                                 tellduslive.DOMAIN),
        async_discover_binary_sensor)


class TelldusLiveSensor(TelldusLiveEntity, BinarySensorDevice):
    """Representation of a Tellstick sensor."""

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.is_on
