"""The CatGenie integration."""

from __future__ import annotations

from contextlib import AsyncExitStack

from catgenie import CatGenieAuth, CatGenieClient, Credentials
from catgenie.exceptions import CatGenieAuthenticationError, CatGenieException

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .coordinator import CatGenieConfigEntry, CatGenieCoordinator, CatGenieRuntimeData

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: CatGenieConfigEntry) -> bool:
    """Set up CatGenie from a config entry."""
    credentials = Credentials(refresh_token=entry.data[CONF_TOKEN])
    stack = AsyncExitStack()

    auth = CatGenieAuth()
    await stack.enter_async_context(auth)
    auth.credentials = credentials

    # Obtain a fresh access token using the stored refresh token
    try:
        credentials = await auth.refresh()
    except CatGenieAuthenticationError as err:
        await stack.aclose()
        raise ConfigEntryAuthFailed(
            translation_domain="catgenie",
            translation_key="authentication_failed",
        ) from err
    except (CatGenieException, ConnectionError) as err:
        await stack.aclose()
        raise ConfigEntryNotReady(
            translation_domain="catgenie",
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Persist rotated refresh token so subsequent startups use the latest token
    if credentials.refresh_token != entry.data[CONF_TOKEN]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_TOKEN: credentials.refresh_token}
        )

    client = CatGenieClient(credentials)
    await stack.enter_async_context(client)
    client.set_auth(auth)

    coordinator = CatGenieCoordinator(hass, entry, client, auth)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = CatGenieRuntimeData(
        stack=stack,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CatGenieConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.stack.aclose()
    return unload_ok
