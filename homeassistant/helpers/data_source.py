"""Data sources for scripts and actions."""

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.loader import IntegrationNotFound, async_get_integration


async def async_provide_data_source(hass: HomeAssistant, config: dict[str, Any]) -> Any:
    """Perform the data source fetch."""
    try:
        integration = await async_get_integration(hass, "data_source")
    except IntegrationNotFound:
        raise vol.Invalid("Data Sources platform 'data_source' not found") from None
    return await integration.get_component().async_get_data_source(
        hass, config[CONF_PLATFORM], config
    )
