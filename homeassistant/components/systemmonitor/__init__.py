"""The systemmonitor integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_RESOURCES, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ARG, DOMAIN
from .sensor import SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TYPE): vol.In(SENSOR_TYPES),
        vol.Optional(CONF_ARG): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [TYPE_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Systemmonitor from yaml config."""
    _LOGGER.debug(config)
    _config: list[ConfigType] | None
    if not (_config := config.get(DOMAIN)):
        return True

    _LOGGER.debug(_config)
    resource_config = {CONF_RESOURCES: _config}
    await discovery.async_load_platform(
        hass,
        Platform.SENSOR,
        DOMAIN,
        resource_config,
        config,
    )

    return True
