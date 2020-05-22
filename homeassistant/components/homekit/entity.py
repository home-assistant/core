"""The homekit integration base entity."""

from pyhap.const import __version__ as pyhap_version

from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity

from .const import BRIDGE_SERIAL_NUMBER, DOMAIN, MANUFACTURER


class HomeKitEntity(Entity):
    """Base class for homekit entities."""

    def __init__(self, config_entry, bridge_mac, bridge_name):
        """Initialize the sensor."""
        super().__init__()
        self._bridge_mac = bridge_mac
        self._bridge_name = bridge_name
        self._config_entry = config_entry

    @property
    def device_info(self):
        """Entity device info."""
        connection = (device_registry.CONNECTION_NETWORK_MAC, self._bridge_mac)
        identifier = (DOMAIN, self._config_entry.entry_id, BRIDGE_SERIAL_NUMBER)
        device_info = {
            # identifiers will be stable for the life of the config entry
            "identifiers": {identifier},
            "name": self._bridge_name,
            "manufacturer": MANUFACTURER,
            # connections can change if the pairing is manually reset
            # of the homekit state files are deleted (which happens
            # more than we would hope). We still need connections
            # so we can identify the bridge on the network via zeroconf
            # so it can be excluded from homekit_controller.
            "connections": {connection},
            "model": "Home Assistant HomeKit Bridge",
            "via_device": (DOMAIN, self._bridge_mac),
            "sw_version": pyhap_version,
        }
        return device_info

    @property
    def should_poll(self):
        """Update from callback."""
        return False

    async def async_remove(self):
        """Remove from entity registry on remove."""
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()
        if entity_registry.async_get(self.entity_id):
            entity_registry.async_remove(self.entity_id)
        return await super().async_remove()
