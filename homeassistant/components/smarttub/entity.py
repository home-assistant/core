"""SmartTub integration."""
import logging

import smarttub

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .const import DOMAIN
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


class SmartTubEntity(CoordinatorEntity):
    """Base class for SmartTub entities."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, spa: smarttub.Spa, entity_name
    ):
        """Initialize the entity.

        Given a spa id and a short name for the entity, we provide basic device
        info, name, unique id, etc. for all derived entities.
        """

        super().__init__(coordinator)
        self.spa = spa
        self._entity_name = entity_name

    @property
    def device_info(self) -> str:
        """Return device info."""
        return {"identifiers": {(DOMAIN, self.spa.id)}}

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        spa_name = get_spa_name(self.spa)
        return f"{spa_name} {self._entity_name}"

    @property
    def unique_id(self) -> str:
        """Return a unique id for the entity."""
        return f"{self.spa.id}-{slugify(self._entity_name)}"

    def get_spa_status(self, path):
        """Retrieve a value from the data returned by Spa.get_status().

        Nested keys can be specified by a dotted path, e.g.
        status['foo']['bar'] is 'foo.bar'.
        """

        status = self.coordinator.data[self.spa.id].get("status")
        if status is None:
            return None

        for key in path.split("."):
            status = status[key]

        return status
