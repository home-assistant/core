"""The Willow integration."""

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from . import api
from .client import WillowClient
from .const import DOMAIN, OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET
from .coordinator import WillowDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type WillowConfigEntry = ConfigEntry[api.WillowRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Willow integration."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(OAUTH2_CLIENT_ID, OAUTH2_CLIENT_SECRET, name="Willow"),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: WillowConfigEntry) -> bool:
    """Set up Willow from a config entry."""
    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            "OAuth2 implementation temporarily unavailable, will retry"
        ) from err

    session = OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    client = WillowClient(
        aiohttp_client.async_get_clientsession(hass),
        session.token[CONF_ACCESS_TOKEN],
    )
    coordinator = WillowDataUpdateCoordinator(
        hass,
        entry,
        client,
        session,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = api.WillowRuntimeData(
        coordinator=coordinator,
        profile=coordinator.profile,
    )

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WillowConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
