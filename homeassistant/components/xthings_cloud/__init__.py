"""Xthings Cloud integration for Home Assistant."""

from __future__ import annotations

import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import XthingsCloudApiClient, XthingsCloudAuthError
from .const import CONF_REFRESH_TOKEN, CONF_REMOTE_ACCESS, CONF_TOKEN, DOMAIN, LOGGER, PLATFORMS
from .coordinator import XthingsCloudCoordinator
from .remote_access import async_disable_remote_access, async_enable_remote_access


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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
            )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    await coordinator.async_start_websocket()

    # Handle remote access based on options
    if entry.options.get(CONF_REMOTE_ACCESS, False):
        from homeassistant.helpers.instance_id import async_get as async_get_instance_id
        instance_id = await async_get_instance_id(hass)
        await async_enable_remote_access(hass, client, instance_id)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_stop_websocket()

    # Clean up FRP config if remote access was enabled
    if entry.options.get(CONF_REMOTE_ACCESS, False):
        await async_disable_remote_access(hass)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_options_updated(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update."""
    coordinator: XthingsCloudCoordinator = hass.data[DOMAIN][entry.entry_id]
    if entry.options.get(CONF_REMOTE_ACCESS, False):
        from homeassistant.helpers.instance_id import async_get as async_get_instance_id
        instance_id = await async_get_instance_id(hass)
        await async_enable_remote_access(hass, coordinator.client, instance_id)
    else:
        await async_disable_remote_access(hass)


@callback
def _async_update_token(
    hass: HomeAssistant,
    entry: ConfigEntry,
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
