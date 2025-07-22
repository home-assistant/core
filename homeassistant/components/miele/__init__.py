"""The Miele integration."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponseError

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import AsyncConfigEntryAuth
from .const import DOMAIN
from .coordinator import MieleConfigEntry, MieleDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]


async def async_setup_entry(hass: HomeAssistant, entry: MieleConfigEntry) -> bool:
    """Set up Miele from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)
    auth = AsyncConfigEntryAuth(async_get_clientsession(hass), session)
    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="config_entry_auth_failed",
            ) from err
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err
    except ClientError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_ready",
        ) from err

    # Setup MieleAPI and coordinator for data fetch
    coordinator = MieleDataUpdateCoordinator(hass, auth)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_create_background_task(
        hass,
        coordinator.api.listen_events(
            data_callback=coordinator.callback_update_data,
            actions_callback=coordinator.callback_update_actions,
        ),
        "pymiele event listener",
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MieleConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: MieleConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in config_entry.runtime_data.data.devices
    )
