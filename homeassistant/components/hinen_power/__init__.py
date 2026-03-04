"""Support for Hinen Power."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
    async_get_config_entry_implementation,
    async_register_implementation,
)

from . import application_credentials
from .auth_config import AsyncConfigEntryAuth
from .const import DOMAIN
from .coordinator import (
    HinenDataUpdateCoordinator,
    HinenPowerConfigEntry,
    HinenPowerRuntimeData,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HinenPowerConfigEntry) -> bool:
    """Set up the Hinen Auth component."""
    hinen_auth_impl: AbstractOAuth2Implementation = (
        await application_credentials.async_get_auth_implementation(
            hass,
            DOMAIN,
            ClientCredential(
                entry.data["token"]["client_id"], entry.data["token"]["client_secret"]
            ),
        )
    )
    async_register_implementation(hass, DOMAIN, hinen_auth_impl)
    implementation = await async_get_config_entry_implementation(hass, entry)
    auth = AsyncConfigEntryAuth(hass, OAuth2Session(hass, entry, implementation))

    try:
        await auth.check_and_refresh_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err

    coordinator = HinenDataUpdateCoordinator(hass, entry, auth)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HinenPowerRuntimeData(
        coordinator=coordinator,
        auth=auth,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HinenPowerConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
