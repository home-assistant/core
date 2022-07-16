"""The Twitch integration."""
from __future__ import annotations

import logging

from twitchAPI.twitch import Twitch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_REFRESH_TOKEN, DOMAIN, OAUTH_SCOPES
from .coordinator import TwitchUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Twitch from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    await session.async_ensure_token_valid()

    client_id = entry.data["auth_implementation"].split("_")[1]
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

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update listener."""
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
        self._service_id = service_id
        self._service_name = service_name
        self._key = key

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Twitch instance."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=self._service_name,
        )

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key
