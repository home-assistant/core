"""Support for binary sensors using Tellstick Net."""

from typing import override

from homeassistant.components import binary_sensor
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TelldusLiveConfigEntry
from .const import DOMAIN, TELLDUS_DISCOVERY_NEW
from .entity import TelldusLiveEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TelldusLiveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up tellduslive sensors dynamically."""

    async def async_discover_binary_sensor(device_id):
        """Discover and add a discovered sensor."""
        async_add_entities([TelldusLiveSensor(config_entry.runtime_data, device_id)])

    async_dispatcher_connect(
        hass,
        TELLDUS_DISCOVERY_NEW.format(binary_sensor.DOMAIN, DOMAIN),
        async_discover_binary_sensor,
    )


class TelldusLiveSensor(TelldusLiveEntity, BinarySensorEntity):
    """Representation of a Tellstick sensor."""

    _attr_name = None

    @property
    @override
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self.device.is_on
