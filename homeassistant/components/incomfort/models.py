"""Models for Intergas InComfort integration."""

from dataclasses import dataclass, field
from typing import Any

from incomfortclient import Gateway as InComfortGateway, Heater as InComfortHeater

from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN


@dataclass
class InComfortData:
    """Keep the Intergas InComfort entry data."""

    client: InComfortGateway
    heaters: list[InComfortHeater] = field(default_factory=list)


DATA_INCOMFORT: HassKey[dict[str, InComfortData]] = HassKey(DOMAIN)


ERROR_STATUS_MAPPING: dict[int, tuple[str, str]] = {
    401: (CONF_PASSWORD, "auth_error"),
    404: ("base", "not_found"),
}


async def async_connect_gateway(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
) -> InComfortData:
    """Validate the configuration."""
    credentials = dict(entry_data)
    hostname = credentials.pop(CONF_HOST)

    client = InComfortGateway(
        hostname, **credentials, session=async_get_clientsession(hass)
    )
    heaters = await client.heaters()

    return InComfortData(client=client, heaters=heaters)
