"""The NextDNS component."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TypeVar

from aiohttp.client_exceptions import ClientConnectorError
from async_timeout import timeout
from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
    ApiError,
    ConnectionStatus,
    InvalidApiKeyError,
    NextDns,
    Settings,
)
from nextdns.model import NextDnsData

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_CONNECTION,
    ATTR_DNSSEC,
    ATTR_ENCRYPTION,
    ATTR_IP_VERSIONS,
    ATTR_PROTOCOLS,
    ATTR_SETTINGS,
    ATTR_STATUS,
    CONF_PROFILE_ID,
    DOMAIN,
    UPDATE_INTERVAL_ANALYTICS,
    UPDATE_INTERVAL_CONNECTION,
    UPDATE_INTERVAL_SETTINGS,
)

CoordinatorDataT = TypeVar("CoordinatorDataT", bound=NextDnsData)


class NextDnsUpdateCoordinator(DataUpdateCoordinator[CoordinatorDataT]):
    """Class to manage fetching NextDNS data API."""

    def __init__(
        self,
        hass: HomeAssistant,
        nextdns: NextDns,
        profile_id: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize."""
        self.nextdns = nextdns
        self.profile_id = profile_id
        self.profile_name = nextdns.get_profile_name(profile_id)
        self.device_info = DeviceInfo(
            configuration_url=f"https://my.nextdns.io/{profile_id}/setup",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, str(profile_id))},
            manufacturer="NextDNS Inc.",
            name=self.profile_name,
        )

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> CoordinatorDataT:
        """Update data via internal method."""
        try:
            async with timeout(10):
                return await self._async_update_data_internal()
        except (ApiError, ClientConnectorError, InvalidApiKeyError) as err:
            raise UpdateFailed(err) from err

    async def _async_update_data_internal(self) -> CoordinatorDataT:
        """Update data via library."""
        raise NotImplementedError("Update method not implemented")


class NextDnsStatusUpdateCoordinator(NextDnsUpdateCoordinator[AnalyticsStatus]):
    """Class to manage fetching NextDNS analytics status data from API."""

    async def _async_update_data_internal(self) -> AnalyticsStatus:
        """Update data via library."""
        return await self.nextdns.get_analytics_status(self.profile_id)


class NextDnsDnssecUpdateCoordinator(NextDnsUpdateCoordinator[AnalyticsDnssec]):
    """Class to manage fetching NextDNS analytics Dnssec data from API."""

    async def _async_update_data_internal(self) -> AnalyticsDnssec:
        """Update data via library."""
        return await self.nextdns.get_analytics_dnssec(self.profile_id)


class NextDnsEncryptionUpdateCoordinator(NextDnsUpdateCoordinator[AnalyticsEncryption]):
    """Class to manage fetching NextDNS analytics encryption data from API."""

    async def _async_update_data_internal(self) -> AnalyticsEncryption:
        """Update data via library."""
        return await self.nextdns.get_analytics_encryption(self.profile_id)


class NextDnsIpVersionsUpdateCoordinator(NextDnsUpdateCoordinator[AnalyticsIpVersions]):
    """Class to manage fetching NextDNS analytics IP versions data from API."""

    async def _async_update_data_internal(self) -> AnalyticsIpVersions:
        """Update data via library."""
        return await self.nextdns.get_analytics_ip_versions(self.profile_id)


class NextDnsProtocolsUpdateCoordinator(NextDnsUpdateCoordinator[AnalyticsProtocols]):
    """Class to manage fetching NextDNS analytics protocols data from API."""

    async def _async_update_data_internal(self) -> AnalyticsProtocols:
        """Update data via library."""
        return await self.nextdns.get_analytics_protocols(self.profile_id)


class NextDnsSettingsUpdateCoordinator(NextDnsUpdateCoordinator[Settings]):
    """Class to manage fetching NextDNS connection data from API."""

    async def _async_update_data_internal(self) -> Settings:
        """Update data via library."""
        return await self.nextdns.get_settings(self.profile_id)


class NextDnsConnectionUpdateCoordinator(NextDnsUpdateCoordinator[ConnectionStatus]):
    """Class to manage fetching NextDNS connection data from API."""

    async def _async_update_data_internal(self) -> ConnectionStatus:
        """Update data via library."""
        return await self.nextdns.connection_status(self.profile_id)


_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
COORDINATORS: list[tuple[str, type[NextDnsUpdateCoordinator], timedelta]] = [
    (ATTR_CONNECTION, NextDnsConnectionUpdateCoordinator, UPDATE_INTERVAL_CONNECTION),
    (ATTR_DNSSEC, NextDnsDnssecUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_ENCRYPTION, NextDnsEncryptionUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_IP_VERSIONS, NextDnsIpVersionsUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_PROTOCOLS, NextDnsProtocolsUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
    (ATTR_SETTINGS, NextDnsSettingsUpdateCoordinator, UPDATE_INTERVAL_SETTINGS),
    (ATTR_STATUS, NextDnsStatusUpdateCoordinator, UPDATE_INTERVAL_ANALYTICS),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NextDNS as config entry."""
    api_key = entry.data[CONF_API_KEY]
    profile_id = entry.data[CONF_PROFILE_ID]

    websession = async_get_clientsession(hass)
    try:
        async with timeout(10):
            nextdns = await NextDns.create(websession, api_key)
    except (ApiError, ClientConnectorError, asyncio.TimeoutError) as err:
        raise ConfigEntryNotReady from err

    tasks = []
    coordinators = {}

    # Independent DataUpdateCoordinator is used for each API endpoint to avoid
    # unnecessary requests when entities using this endpoint are disabled.
    for coordinator_name, coordinator_class, update_interval in COORDINATORS:
        coordinator = coordinator_class(hass, nextdns, profile_id, update_interval)
        tasks.append(coordinator.async_config_entry_first_refresh())
        coordinators[coordinator_name] = coordinator

    await asyncio.gather(*tasks)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
