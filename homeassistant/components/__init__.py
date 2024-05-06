"""Contains components that can be plugged into Home Assistant.

Component design guidelines:
- Each component defines a constant DOMAIN that is equal to its filename.
- Each component that tracks states should create state entity names in the
  format "<DOMAIN>.<OBJECT_ID>".
- Each component should publish services only under its own domain.
"""
from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers.group import expand_entity_ids

_LOGGER = logging.getLogger(__name__)


def is_on(hass: HomeAssistant, entity_id: str | None = None) -> bool:
    """Load up the module to call the is_on method.

    If there is no entity id given we will check all.
    """
    if entity_id:
        entity_ids = expand_entity_ids(hass, [entity_id])
    else:
        entity_ids = hass.states.entity_ids()

    for ent_id in entity_ids:
        domain = split_entity_id(ent_id)[0]

        try:
            component = getattr(hass.components, domain)

        except ImportError:
            _LOGGER.error("Failed to call %s.is_on: component not found", domain)
            continue

        if not hasattr(component, "is_on"):
            _LOGGER.warning("Integration %s has no is_on method", domain)
            continue

        if component.is_on(ent_id):
            return True

    return False
