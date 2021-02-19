"""SmartTub integration."""
import logging

import smarttub

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


class SmartTubEntity(CoordinatorEntity):
    """Base class for SmartTub entities."""

    def __init__(
        self, coordinator: DataUpdateCoordinator, spa: smarttub.Spa, entity_type
    ):
        """Initialize the entity.

        Given a spa id and a short name for the entity, we provide basic device
        info, name, unique id, etc. for all derived entities.
        """

        super().__init__(coordinator)
        self.spa = spa
        self._entity_type = entity_type

    @property
    def device_info(self) -> str:
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self.spa.id)},
            "manufacturer": self.spa.brand,
            "model": self.spa.model,
        }

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        spa_name = get_spa_name(self.spa)
        return f"{spa_name} {self._entity_type}"

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
