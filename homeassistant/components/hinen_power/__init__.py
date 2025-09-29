"""Support for hello auth."""

from __future__ import annotations

from aiohttp.client_exceptions import ClientError, ClientResponseError
from openai import BaseModel

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
    OAuth2Session,
    async_get_config_entry_implementation,
    async_register_implementation,
)

from . import application_credentials
from .auth_config import AsyncConfigEntryAuth
from .const import AUTH, COORDINATOR, DOMAIN
from .coordinator import HinenDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: HinenIntegrationConfigEntry
) -> bool:
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
    await delete_devices(hass, entry, coordinator)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        AUTH: auth,
    }

    entry.runtime_data = HinenClient()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def delete_devices(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: HinenDataUpdateCoordinator
) -> None:
    """Delete all devices created by integration."""
    device_ids = list(coordinator.data)
    device_registry = dr.async_get(hass)
    dev_entries = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for dev_entry in dev_entries:
        if any(identifier[1] in device_ids for identifier in dev_entry.identifiers):
            device_registry.async_update_device(
                dev_entry.id, remove_config_entry_id=entry.entry_id
            )


class HinenClient(BaseModel):
    """hinen client."""


type HinenIntegrationConfigEntry = ConfigEntry[HinenClient]
