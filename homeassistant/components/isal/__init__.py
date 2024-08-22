"""The isal integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers import config_validation as cv

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

DOMAIN = "isal"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up up isal.

    This integration is only used so that isal can be an optional
    dep for aiohttp-fast-zlib.
    """
    return True
