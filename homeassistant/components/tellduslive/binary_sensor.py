"""Support for binary sensors using Tellstick Net."""
from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import tellduslive
from .entry import TelldusLiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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


class TelldusLiveSensor(TelldusLiveEntity, BinarySensorEntity):
    """Representation of a Tellstick sensor."""

    _attr_name = None

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.device.is_on
