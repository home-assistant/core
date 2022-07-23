"""The Twitch integration."""
from __future__ import annotations

import logging

from twitchAPI.twitch import Twitch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow, device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CHANNELS, CONF_REFRESH_TOKEN, DOMAIN, OAUTH_SCOPES
from .coordinator import TwitchUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Set up Twitch from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    await session.async_ensure_token_valid()

    client_id = implementation.__dict__[CONF_CLIENT_ID]
    access_token = entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN]
    refresh_token = entry.data[CONF_TOKEN][CONF_REFRESH_TOKEN]

    client = Twitch(
        app_id=client_id,
        authenticate_app=False,
        target_app_auth_scope=OAUTH_SCOPES,
    )
    client.auto_refresh_auth = False

    await hass.async_add_executor_job(
        client.set_user_authentication,
        access_token,
        OAUTH_SCOPES,
        refresh_token,
        True,
    )

    coordinator = TwitchUpdateCoordinator(hass, _LOGGER, client, entry.options)

    # Set data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    async_cleanup_device_registry(hass=hass, entry=entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


@callback
def async_cleanup_device_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Remove entries from device registry if we no longer track the channel."""
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(
        registry=device_registry,
        config_entry_id=entry.entry_id,
    )
    for device in devices:
        for item in device.identifiers:
            if DOMAIN == item[0] and item[1] not in entry.options[CONF_CHANNELS]:
                _LOGGER.debug(
                    "Unlinking device %s for untracked channel %s from config entry %s",
                    device.id,
                    item[1],
                    entry.entry_id,
                )
                device_registry.async_update_device(
                    device.id, remove_config_entry_id=entry.entry_id
                )
                break


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class TwitchDeviceEntity(CoordinatorEntity[TwitchUpdateCoordinator]):
    """An entity using CoordinatorEntity."""

    def __init__(
        self,
        coordinator: TwitchUpdateCoordinator,
        service_id: str,
        service_name: str,
        key: str,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._attr_unique_id = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, service_id)},
            name=service_name,
            manufacturer="Twitch",
            configuration_url=f"https://twitch.tv/{service_name}",
            entry_type=DeviceEntryType.SERVICE,
        )

        self._service_id = service_id
