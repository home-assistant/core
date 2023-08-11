"""The Honeywell Lyric integration."""
from __future__ import annotations

from datetime import timedelta
from http import HTTPStatus
import logging

from aiohttp.client_exceptions import ClientResponseError
from aiolyric import Lyric
from aiolyric.exceptions import LyricAuthenticationException, LyricException
from aiolyric.objects.device import LyricDevice
from aiolyric.objects.location import LyricLocation
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    ConfigEntryLyricClient,
    LyricLocalOAuth2Implementation,
    OAuth2SessionLyric,
)
from .const import DOMAIN

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Honeywell Lyric from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    if not isinstance(implementation, LyricLocalOAuth2Implementation):
        raise TypeError("Unexpected auth implementation; can't find oauth client id")

    session = aiohttp_client.async_get_clientsession(hass)
    oauth_session = OAuth2SessionLyric(hass, entry, implementation)

    client = ConfigEntryLyricClient(session, oauth_session)

    client_id = implementation.client_id
    lyric = Lyric(client, client_id)

    async def async_update_data(force_refresh_token: bool = False) -> Lyric:
        """Fetch data from Lyric."""
        try:
            if not force_refresh_token:
                await oauth_session.async_ensure_token_valid()
            else:
                await oauth_session.force_refresh_token()
        except ClientResponseError as exception:
            if exception.status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
                raise ConfigEntryAuthFailed from exception
            raise UpdateFailed(exception) from exception

        try:
            async with async_timeout.timeout(60):
                await lyric.get_locations()
            return lyric
        except LyricAuthenticationException as exception:
            # Attempt to refresh the token before failing.
            # Honeywell appear to have issues keeping tokens saved.
            _LOGGER.debug("Authentication failed. Attempting to refresh token")
            if not force_refresh_token:
                return await async_update_data(force_refresh_token=True)
            raise ConfigEntryAuthFailed from exception
        except (LyricException, ClientResponseError) as exception:
            raise UpdateFailed(exception) from exception

    coordinator = DataUpdateCoordinator[Lyric](
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="lyric_coordinator",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=300),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class LyricEntity(CoordinatorEntity[DataUpdateCoordinator[Lyric]]):
    """Defines a base Honeywell Lyric entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[Lyric],
        location: LyricLocation,
        device: LyricDevice,
        key: str,
    ) -> None:
        """Initialize the Honeywell Lyric entity."""
        super().__init__(coordinator)
        self._key = key
        self._location = location
        self._mac_id = device.macID
        self._update_thermostat = coordinator.data.update_thermostat

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return self._key

    @property
    def location(self) -> LyricLocation:
        """Get the Lyric Location."""
        return self.coordinator.data.locations_dict[self._location.locationID]

    @property
    def device(self) -> LyricDevice:
        """Get the Lyric Device."""
        return self.location.devices_dict[self._mac_id]


class LyricDeviceEntity(LyricEntity):
    """Defines a Honeywell Lyric device entity."""

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Honeywell Lyric instance."""
        return DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, self._mac_id)},
            manufacturer="Honeywell",
            model=self.device.deviceModel,
            name=self.device.name,
        )
