"""Siren grouper for EffortlessHome."""

import logging
from functools import cached_property

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)


class SirenGrouper:
    """Class to group all sirens."""

    def __init__(self, hass) -> None:
        """Initialize the siren grouper."""
        self.hass = hass
        self._attr_name = "Siren Grouper"
        _LOGGER.debug("[SirenGrouper] Initialized with hass object.")

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "identifiers": {(DOMAIN, NAME)},
            "name": NAME,
            "manufacturer": NAME,
        }

    @cached_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._attr_name

    async def create_siren_group(self) -> None:
        """Create a group of all sirens."""
        _LOGGER.debug("[SirenGrouper] create_siren_group called.")
        entities = er.async_get(self.hass)
        sirens = [
            entity.entity_id
            for entity in entities.entities.values()
            if entity.domain == "siren"
        ]
        _LOGGER.debug("[SirenGrouper] Found sirens: %s", sirens)
        group_name = "group.all_sirens"
        await self._create_group(group_name, sirens)

    async def _create_group(self, group_name, entity_ids) -> None:  # noqa: ANN001
        """Create a group of entities in Home Assistant."""
        _LOGGER.debug(
            "[SirenGrouper] Creating group '%s' with entities: %s",
            group_name,
            entity_ids,
        )
        service_data = {
            "object_id": group_name.split(".")[-1],
            "name": group_name.split(".")[-1].replace("_", " ").title(),
            "entities": entity_ids,
        }
        await self.hass.services.async_call("group", "set", service_data, blocking=True)
        _LOGGER.debug(
            "[SirenGrouper] Group '%s' created with entities: %s",
            group_name,
            entity_ids,
        )
