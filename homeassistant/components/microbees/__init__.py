"""The microBees integration."""

from dataclasses import dataclass
from http import HTTPStatus
import logging

import aiohttp
from microBeesPy.bee import Bee

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import api
from .const import ACCESS_TOKEN, AUTH, BEES, CONNECTOR, DOMAIN, PLATFORMS
from .microbees import MicroBeesConnector

_LOGGER = logging.getLogger(__name__)


@dataclass
class HomeAssistantMicroBeesData:
    """Microbees data stored in the Home Assistant data object."""

    client: MicroBeesConnector
    bees: list[Bee]
    session: config_entry_oauth2_flow.OAuth2Session


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, domain=DOMAIN
) -> bool:
    """Set up microBees from a config entry."""
    hass.data[DOMAIN] = {}
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        if ex.status in (
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        ):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex
    hass.data[DOMAIN][entry.entry_id] = {
        AUTH: api.ConfigEntryAuth(aiohttp_client.async_get_clientsession(hass), session)
    }
    microbees = MicroBeesConnector(token=session.token[ACCESS_TOKEN])
    hass.data[DOMAIN][CONNECTOR] = microbees
    bees = await microbees.getBees()

    hass.data[DOMAIN][BEES] = bees
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HomeAssistantMicroBeesData(
        client=microbees,
        bees=bees,
        session=session,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
