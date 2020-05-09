"""The homekitintegration base entity."""

from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER


class HomeKitEntity(Entity):
    """Base class for homekit entities."""

    def __init__(self, bridge_mac, acc, model):
        """Initialize the sensor."""
        super().__init__()
        self.model = model
        self.acc = acc
        self.bridge_mac = bridge_mac
        self.base_unique_id = f"{bridge_mac}_{acc.aid}"

    @property
    def device_info(self):
        """Entity device info."""
        device_info = {
            "identifiers": {(DOMAIN, self.base_unique_id)},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": self.model,
            "via_device": (DOMAIN, self.bridge_mac),
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
