"""
Manage allocation of accessory ID's.

HomeKit needs to allocate unique numbers to each accessory. These need to
be stable between reboots and upgrades.

Using a hash function to generate them means collisions. It also means you
can't change the hash without causing breakages for HA users.

This module generates and stores them in a HA storage.
"""
import hashlib
import logging
import random
from zlib import adler32

from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from .const import DOMAIN

AID_MANAGER_STORAGE_KEY = f"{DOMAIN}-aid-storage"
AID_MANAGER_STORAGE_VERSION = 1
AID_MANAGER_SAVE_DELAY = 2

_LOGGER = logging.getLogger(__name__)


def generate_aids(unique_id, entity_id):
    """Generate accessory aid with zlib adler32."""

    # Backward compatibility: Previously HA used to *only* do adler32 on the entity id.
    # Not stable if entity ID changes
    # Not robust against collisions
    yield adler32(entity_id.encode("utf-8"))

    # Use adler32 on a sha of the unique id
    yield adler32(hashlib.sha512(unique_id.encode("utf-8")).digest())

    # If called again resort to random allocations.
    # Given the size of the range its unlikely we'll encounter duplicates
    # But try a few times regardless
    for _ in range(5):
        yield random.randrange(2, 18446744073709551615)


class AccessoryAidStorage:
    """
    Holds a map of entity ID to HomeKit ID.

    Will generate new ID's, ensure they are unique and store them to make sure they
    persist over reboots.
    """

    def __init__(self, hass):
        """Create a new entity map store."""
        self.hass = hass
        self.store = Store(hass, AID_MANAGER_STORAGE_VERSION, AID_MANAGER_STORAGE_KEY)
        self.allocations = {}
        self.allocated_aids = set()

        self._entity_registry = None

    async def async_initialize(self):
        """Load the latest AID data."""
        self._entity_registry = (
            await self.hass.helpers.entity_registry.async_get_registry()
        )

        raw_storage = await self.store.async_load()
        if not raw_storage:
            # There is no data about aid allocations yet
            return

        self.allocations = raw_storage.get("unique_ids", {})
        self.allocated_aids = set(self.allocations.values())

    def get_or_allocate_aid_for_entity_id(self, entity_id):
        """Generate a stable aid for an entity id."""
        entity = self._entity_registry.async_get(entity_id)
        if entity:
            return self._get_or_allocate_aid(entity.unique_id, entity.entity_id)

        _LOGGER.warning(
            "Entity '%s' does not have a stable unique identifier so aid allocation will be unstable and may cause collisions",
            entity_id,
        )
        return adler32(entity_id.encode("utf-8"))

    def _get_or_allocate_aid(self, unique_id, entity_id):
        """Allocate (and return) a new aid for an accessory."""
        if unique_id in self.allocations:
            return self.allocations[unique_id]

        for aid in generate_aids(unique_id, entity_id):
            if aid in (0, 1):
                continue
            if aid not in self.allocated_aids:
                self.allocations[unique_id] = aid
                self.allocated_aids.add(aid)
                self._async_schedule_save()
                return aid

        raise ValueError(
            f"Unable to generate unique aid allocation for {entity_id} [{unique_id}]"
        )

    def delete_aid(self, unique_id):
        """Delete an aid allocation."""
        if unique_id not in self.allocations:
            return

        aid = self.allocations.pop(unique_id)
        self.allocated_aids.discard(aid)
        self._async_schedule_save()

    @callback
    def _async_schedule_save(self):
        """Schedule saving the entity map cache."""
        self.store.async_delay_save(self._data_to_save, AID_MANAGER_SAVE_DELAY)

    @callback
    def _data_to_save(self):
        """Return data of entity map to store in a file."""
        return {"unique_ids": self.allocations}
