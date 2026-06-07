"""The Culiplan integration."""

from dataclasses import dataclass
import logging

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType

from .api import CuliplanApiClient
from .const import DOMAIN, OAUTH_CLIENT_ID, PLATFORMS
from .coordinator import CuliplanCoordinator
from .llm_api import async_register_llm_api, async_unregister_llm_api

_LOGGER = logging.getLogger(__name__)

# This integration is config_entry-only — there is no YAML schema.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class CuliplanRuntimeData:
    """Per-entry runtime data carried on ``ConfigEntry.runtime_data``."""

    client: CuliplanApiClient
    coordinator: CuliplanCoordinator


type CuliplanConfigEntry = ConfigEntry[CuliplanRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Culiplan integration.

    Auto-imports the public OAuth client credential so the user skips the
    "Add application credentials" dialog and goes straight to consent.
    """
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(client_id=OAUTH_CLIENT_ID, client_secret=""),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: CuliplanConfigEntry) -> bool:
    """Set up Culiplan from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    await session.async_ensure_token_valid()

    client = CuliplanApiClient(
        session=aiohttp_client.async_get_clientsession(hass),
        access_token=session.token["access_token"],
    )

    coordinator = CuliplanCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_start()

    # Register the coordinator's teardown BEFORE forwarding to platforms so
    # a platform-setup failure still closes the Socket.IO connection.
    entry.async_on_unload(coordinator.async_stop)

    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async_register_llm_api(hass)
    entry.async_on_unload(lambda: async_unregister_llm_api(hass))
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: CuliplanConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: CuliplanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
