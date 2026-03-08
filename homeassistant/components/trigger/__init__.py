"""Integration to load trigger platforms from specific integrations."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import async_register_trigger_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import IntegrationNotFound, async_get_integration

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema("trigger")

DEFAULT_TRIGGER_DOMAINS = ("door",)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up trigger platforms from specific integrations."""
    for domain in DEFAULT_TRIGGER_DOMAINS:
        try:
            integration = await async_get_integration(hass, domain)
        except IntegrationNotFound:
            _LOGGER.debug("Integration %s not found, skipping", domain)
            continue
        try:
            platform = await integration.async_get_platform("trigger")
        except ImportError:
            _LOGGER.debug("Integration %s does not provide a trigger platform", domain)
            continue
        await async_register_trigger_platform(hass, domain, platform)

    return True
