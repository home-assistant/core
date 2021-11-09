"""Utility functions for triggers."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant import exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, template

_LOGGER = logging.getLogger(__name__)


def validate_entities_or_template_of_entities(
    value: Any, hass: HomeAssistant = None, variables: Any = None
):
    """Return List of Entity IDs, directly configured or from a template."""
    if value is None:
        raise vol.Invalid("Entity IDs can not be None")
    if isinstance(value, str):
        if value.startswith("{"):
            value = cv.template(value)
    if isinstance(value, template.Template):
        if hass:
            try:
                value.hass = hass
                value = value.async_render(variables, limited=True)
                return cv.entity_ids(value)
            except (exceptions.TemplateError, vol.Invalid, TypeError):
                _LOGGER.error("Invalid Template! Must return list of entities")
                return []
        else:
            return value
    return cv.entity_ids(value)
