"""Location based integration matching.

Finds the integrations that serve the country of the home location.
Integrations list the countries they serve with the locations key in their
manifest.
"""

from typing import Any

import probatio

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_locations

from .const import DOMAIN

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up location based integration matching."""
    websocket_api.async_register_command(hass, websocket_integrations)
    return True


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "location/integrations"})
@websocket_api.async_response
async def websocket_integrations(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the integrations serving the country of the home location.

    Maps each domain to the country it serves.
    """
    country = hass.config.country
    domains = (await async_get_locations(hass)).get(country, []) if country else []
    connection.send_result(msg["id"], {domain: [country] for domain in sorted(domains)})
