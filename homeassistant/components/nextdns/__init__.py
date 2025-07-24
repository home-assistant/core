"""The NextDNS component."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

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
from tenacity import RetryError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
)
from .coordinator import (
    NextDnsConnectionUpdateCoordinator,
    NextDnsDnssecUpdateCoordinator,
    NextDnsEncryptionUpdateCoordinator,
    NextDnsIpVersionsUpdateCoordinator,
    NextDnsProtocolsUpdateCoordinator,
    NextDnsSettingsUpdateCoordinator,
    NextDnsStatusUpdateCoordinator,
    NextDnsUpdateCoordinator,
)

type NextDnsConfigEntry = ConfigEntry[NextDnsData]


@dataclass
class NextDnsData:
    """Data for the NextDNS integration."""

    connection: NextDnsUpdateCoordinator[ConnectionStatus]
    dnssec: NextDnsUpdateCoordinator[AnalyticsDnssec]
    encryption: NextDnsUpdateCoordinator[AnalyticsEncryption]
    ip_versions: NextDnsUpdateCoordinator[AnalyticsIpVersions]
    protocols: NextDnsUpdateCoordinator[AnalyticsProtocols]
    settings: NextDnsUpdateCoordinator[Settings]
    status: NextDnsUpdateCoordinator[AnalyticsStatus]


PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
COORDINATORS: list[tuple[str, type[NextDnsUpdateCoordinator]]] = [
    (ATTR_CONNECTION, NextDnsConnectionUpdateCoordinator),
    (ATTR_DNSSEC, NextDnsDnssecUpdateCoordinator),
    (ATTR_ENCRYPTION, NextDnsEncryptionUpdateCoordinator),
    (ATTR_IP_VERSIONS, NextDnsIpVersionsUpdateCoordinator),
    (ATTR_PROTOCOLS, NextDnsProtocolsUpdateCoordinator),
    (ATTR_SETTINGS, NextDnsSettingsUpdateCoordinator),
    (ATTR_STATUS, NextDnsStatusUpdateCoordinator),
]


async def async_setup_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Set up NextDNS as config entry."""
    api_key = entry.data[CONF_API_KEY]
    profile_id = entry.data[CONF_PROFILE_ID]

    websession = async_get_clientsession(hass)
    try:
        nextdns = await NextDns.create(websession, api_key)
    except (ApiError, ClientConnectorError, RetryError, TimeoutError) as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={
                "entry": entry.title,
                "error": repr(err),
            },
        ) from err
    except InvalidApiKeyError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
            translation_placeholders={"entry": entry.title},
        ) from err

    tasks = []
    coordinators = {}

    # Independent DataUpdateCoordinator is used for each API endpoint to avoid
    # unnecessary requests when entities using this endpoint are disabled.
    for coordinator_name, coordinator_class in COORDINATORS:
        coordinator = coordinator_class(hass, entry, nextdns, profile_id)
        tasks.append(coordinator.async_config_entry_first_refresh())
        coordinators[coordinator_name] = coordinator

    await asyncio.gather(*tasks)

    entry.runtime_data = NextDnsData(**coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
