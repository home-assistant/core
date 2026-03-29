"""The UniFi Access integration."""

from __future__ import annotations

from unifi_access_api import ApiAuthError, ApiConnectionError, UnifiAccessApiClient

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN
from .coordinator import UnifiAccessConfigEntry, UnifiAccessCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
    Platform.IMAGE,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: UnifiAccessConfigEntry) -> bool:
    """Set up UniFi Access from a config entry."""
    session = async_get_clientsession(hass, verify_ssl=entry.data[CONF_VERIFY_SSL])

    client = UnifiAccessApiClient(
        host=entry.data[CONF_HOST],
        api_token=entry.data[CONF_API_TOKEN],
        session=session,
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )

    try:
        await client.authenticate()
    except ApiAuthError as err:
        async_create_issue(
            hass,
            DOMAIN,
            "api_token_expired",
            is_fixable=True,
            is_persistent=True,
            learn_more_url="https://www.home-assistant.io/integrations/unifi_access/",
            severity=IssueSeverity.ERROR,
            translation_key="api_token_expired",
            translation_placeholders={"host": entry.data[CONF_HOST]},
            data={"entry_id": entry.entry_id},
        )
        raise ConfigEntryAuthFailed(
            f"Authentication failed for UniFi Access at {entry.data[CONF_HOST]}"
        ) from err
    except ApiConnectionError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to UniFi Access at {entry.data[CONF_HOST]}"
        ) from err

    async_delete_issue(hass, DOMAIN, "api_token_expired")

    coordinator = UnifiAccessCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(client.close)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: UnifiAccessConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
