"""Xthings Cloud integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ha_xthings_cloud import XthingsCloudApiClient, XthingsCloudAuthError
from .const import CONF_REFRESH_TOKEN, CONF_TOKEN, PLATFORMS
from .coordinator import XthingsCloudCoordinator

XthingsCloudConfigEntry = ConfigEntry[XthingsCloudCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Set up config entry."""
    session = async_get_clientsession(hass)
    client = XthingsCloudApiClient(session, token=entry.data[CONF_TOKEN])

    coordinator = XthingsCloudCoordinator(hass, client, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except XthingsCloudAuthError:
        refresh_token = entry.data.get(CONF_REFRESH_TOKEN)
        if refresh_token:
            try:
                token_data = await client.async_refresh_token(refresh_token)
                _async_update_token(hass, entry, token_data)
                await coordinator.async_config_entry_first_refresh()
            except XthingsCloudAuthError as err:
                raise ConfigEntryAuthFailed(
                    "Token refresh failed, re-authentication required"
                ) from err
        else:
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            ) from None

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_websocket()

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: XthingsCloudConfigEntry
) -> bool:
    """Unload config entry."""
    coordinator: XthingsCloudCoordinator = entry.runtime_data
    await coordinator.async_stop_websocket()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def _async_update_token(
    hass: HomeAssistant,
    entry: XthingsCloudConfigEntry,
    token_data: dict,
) -> None:
    """Update token in config entry data."""
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_TOKEN: token_data["token"],
            CONF_REFRESH_TOKEN: token_data.get("refresh_token", ""),
        },
    )
