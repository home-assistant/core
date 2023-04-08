"""The file component."""

import logging
from os import path

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


DOMAIN = "file"

WRITE_PARAM_FILENAME = "filename"
WRITE_PARAM_CONTENT = "content"
WRITE_PARAM_MODE = "mode"

CONF_ALLOWLIST_WRITE_DIRS = "allowlist_write_dirs"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_ALLOWLIST_WRITE_DIRS, default=[]): vol.All(
                    cv.ensure_list, [cv.path]
                )
            }
        )
    },
    required=False,
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the file write service."""

    allowlist_write_dirs = [
        path.normpath(hass.config.path(p) + path.sep)
        for p in config.get(DOMAIN, {}).get(CONF_ALLOWLIST_WRITE_DIRS, [])
    ]

    @callback
    def write(call: ServiceCall) -> None:
        """Write a file."""
        filename = call.data[WRITE_PARAM_FILENAME]
        content = call.data[WRITE_PARAM_CONTENT]
        mode = call.data.get(WRITE_PARAM_MODE, "w")

        filepath = path.normpath(hass.config.path(filename))

        if not any(path.commonpath([filepath, p]) == p for p in allowlist_write_dirs):
            _LOGGER.error("Path is not allowed: %s", filepath)
            raise ValueError("Path is not allowed: %s" % filepath)

        with open(filepath, mode, encoding="utf8") as file:
            file.write(content)

    hass.services.async_register(DOMAIN, "write", write)

    return True
