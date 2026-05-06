"""The CatGenie integration."""

from __future__ import annotations

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

    auth = CatGenieAuth()
    auth.credentials = credentials

    # Obtain a fresh access token using the stored refresh token
    try:
        credentials = await auth.refresh()
    except CatGenieAuthenticationError as err:
        await auth.async_close()
        raise ConfigEntryAuthFailed(
            translation_domain="catgenie",
            translation_key="authentication_failed",
        ) from err
    except (CatGenieException, ConnectionError) as err:
        await auth.async_close()
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
    client.set_auth(auth)

    coordinator = CatGenieCoordinator(hass, entry, client, auth)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.async_close()
        await auth.async_close()
        raise

    entry.runtime_data = CatGenieRuntimeData(
        auth=auth,
        client=client,
        coordinator=coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CatGenieConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.auth.async_close()
        await entry.runtime_data.client.async_close()
    return unload_ok
