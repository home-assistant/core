"""The TP-Link Omada integration."""
from __future__ import annotations

from tplink_omada_client.exceptions import (
    ConnectionFailed,
    LoginFailed,
    OmadaClientException,
    UnsupportedControllerVersion,
)
from tplink_omada_client.omadaclient import OmadaSite

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .config_flow import CONF_SITE, create_omada_client
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TP-Link Omada from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    try:
        client = await create_omada_client(hass, entry.data)
        await client.login()

    except (LoginFailed, UnsupportedControllerVersion) as ex:
        raise ConfigEntryAuthFailed(
            f"Omada controller refused login attempt: {ex}"
        ) from ex
    except ConnectionFailed as ex:
        raise ConfigEntryNotReady(
            f"Omada controller could not be reached: {ex}"
        ) from ex

    except OmadaClientException as ex:
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Omada controller: {ex}"
        ) from ex

    site_client = await client.get_site_client(OmadaSite(None, entry.data[CONF_SITE]))

    hass.data[DOMAIN][entry.entry_id] = site_client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
