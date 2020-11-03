"""Shelly helpers functions."""

import logging

_LOGGER = logging.getLogger(__name__)


async def async_remove_entity_by_domain(hass, domain, unique_id):
    """Remove entity by domain."""
    entity_reg = await hass.helpers.entity_registry.async_get_registry()
    for entry in entity_reg.entities.values():
        if entry.domain == domain and entry.unique_id == unique_id:
            entity_reg.async_remove(entry.entity_id)
            _LOGGER.debug("Removed %s domain for %s", domain, entry.original_name)
            break
