"""Platform for Mazda lock integration."""

from homeassistant.components.lock import LockEntity

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the lock platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    entities = []

    for index, _ in enumerate(coordinator.data):
        entities.append(MazdaLock(client, coordinator, index))

    async_add_entities(entities)


class MazdaLock(MazdaEntity, LockEntity):
    """Class for the lock."""

    @property
    def name(self):
        """Return the name of the entity."""
        vehicle_name = self.get_vehicle_name()
        return f"{vehicle_name} Lock"

    @property
    def unique_id(self):
        """Return a unique identifier for this entity."""
        return self.vin

    @property
    def is_locked(self):
        """Return true if lock is locked."""
        return self.client.get_assumed_lock_state(self.vehicle_id)

    async def async_lock(self, **kwargs):
        """Lock the vehicle doors."""
        await self.client.lock_doors(self.vehicle_id)

        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        """Unlock the vehicle doors."""
        await self.client.unlock_doors(self.vehicle_id)

        self.async_write_ha_state()
