"""NextDns coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypeVar

from aiohttp.client_exceptions import ClientConnectorError
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
from tenacity import RetryError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import NextDnsConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CoordinatorDataT = TypeVar("CoordinatorDataT", bound=NextDnsData)


class NextDnsUpdateCoordinator(DataUpdateCoordinator[CoordinatorDataT]):
    """Class to manage fetching NextDNS data API."""

    config_entry: NextDnsConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NextDnsConfigEntry,
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

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> CoordinatorDataT:
        """Update data via internal method."""
        try:
            return await self._async_update_data_internal()
        except (
            ApiError,
            ClientConnectorError,
            RetryError,
        ) as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                    "error": repr(err),
                },
            ) from err
        except InvalidApiKeyError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"entry": self.config_entry.title},
            ) from err

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
