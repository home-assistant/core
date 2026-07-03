"""The NextDNS component."""

import asyncio
from dataclasses import dataclass
from types import MappingProxyType

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

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

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
    SUBENTRY_TYPE_PROFILE,
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
class NextDnsCoordinators:
    """Coordinators for a NextDNS profile."""

    connection: NextDnsUpdateCoordinator[ConnectionStatus]
    dnssec: NextDnsUpdateCoordinator[AnalyticsDnssec]
    encryption: NextDnsUpdateCoordinator[AnalyticsEncryption]
    ip_versions: NextDnsUpdateCoordinator[AnalyticsIpVersions]
    protocols: NextDnsUpdateCoordinator[AnalyticsProtocols]
    settings: NextDnsUpdateCoordinator[Settings]
    status: NextDnsUpdateCoordinator[AnalyticsStatus]


@dataclass
class NextDnsData:
    """Runtime data for the NextDNS integration."""

    client: NextDns
    profiles: dict[str, NextDnsCoordinators]


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up NextDNS."""
    await async_migrate_integration(hass)
    return True


async def async_migrate_integration(hass: HomeAssistant) -> None:
    """Migrate integration entry structure."""
    # Make sure we get enabled config entries first
    entries = sorted(
        hass.config_entries.async_entries(DOMAIN),
        key=lambda e: e.disabled_by is not None,
    )
    if not any(entry.version == 1 for entry in entries):
        return

    api_keys_entries: dict[str, tuple[NextDnsConfigEntry, bool]] = {}
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    for entry in entries:
        profile_id = entry.data[CONF_PROFILE_ID]
        profile_name = entry.title

        subentry = ConfigSubentry(
            data=MappingProxyType({CONF_PROFILE_ID: profile_id}),
            subentry_type=SUBENTRY_TYPE_PROFILE,
            title=profile_name,
            unique_id=profile_id,
        )

        if entry.data[CONF_API_KEY] not in api_keys_entries:
            all_disabled = all(
                e.disabled_by is not None
                for e in entries
                if e.data[CONF_API_KEY] == entry.data[CONF_API_KEY]
            )
            api_keys_entries[entry.data[CONF_API_KEY]] = (entry, all_disabled)

        parent_entry, all_disabled = api_keys_entries[entry.data[CONF_API_KEY]]

        hass.config_entries.async_add_subentry(parent_entry, subentry)

        entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        device = device_registry.async_get_device(identifiers={(DOMAIN, profile_id)})

        for entity_entry in entities:
            entity_disabled_by = entity_entry.disabled_by
            if (
                entity_disabled_by is er.RegistryEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                # Device and entity registries don't update the disabled_by flag
                # when moving a device or entity from one config entry to another,
                # so we need to do it manually.
                entity_disabled_by = (
                    er.RegistryEntryDisabler.DEVICE
                    if device
                    else er.RegistryEntryDisabler.USER
                )
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                config_entry_id=parent_entry.entry_id,
                config_subentry_id=subentry.subentry_id,
                disabled_by=entity_disabled_by,
            )

        if device is not None:
            # Device and entity registries don't update the disabled_by flag when
            # moving a device or entity from one config entry to another, so we
            # need to do it manually.
            device_disabled_by = device.disabled_by
            if (
                device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
                and not all_disabled
            ):
                device_disabled_by = dr.DeviceEntryDisabler.USER
            device_registry.async_update_device(
                device.id,
                disabled_by=device_disabled_by,
                new_identifiers={
                    (DOMAIN, f"{parent_entry.entry_id}_{subentry.subentry_id}")
                },
                add_config_subentry_id=subentry.subentry_id,
                add_config_entry_id=parent_entry.entry_id,
            )
            if parent_entry.entry_id != entry.entry_id:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                )
            else:
                device_registry.async_update_device(
                    device.id,
                    remove_config_entry_id=entry.entry_id,
                    remove_config_subentry_id=None,
                )

        if parent_entry.entry_id != entry.entry_id:
            await hass.config_entries.async_remove(entry.entry_id)
        else:
            hass.config_entries.async_update_entry(
                entry,
                data={CONF_API_KEY: entry.data[CONF_API_KEY]},
                title="NextDNS",
                version=2,
                unique_id=None,
            )


async def async_setup_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Set up NextDNS as config entry."""
    api_key = entry.data[CONF_API_KEY]

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

    profiles: dict[str, NextDnsCoordinators] = {}

    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_PROFILE):
        subentry_id = subentry.subentry_id
        profile_id = subentry.data[CONF_PROFILE_ID]
        tasks = []
        coordinators = {}

        # Independent DataUpdateCoordinator is used for each API endpoint to avoid
        # unnecessary requests when entities using this endpoint are disabled.
        for coordinator_name, coordinator_class in COORDINATORS:
            coordinator = coordinator_class(
                hass, entry, nextdns, profile_id, subentry_id
            )
            tasks.append(coordinator.async_config_entry_first_refresh())
            coordinators[coordinator_name] = coordinator

        await asyncio.gather(*tasks)

        profiles[subentry_id] = NextDnsCoordinators(**coordinators)

    entry.runtime_data = NextDnsData(client=nextdns, profiles=profiles)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: NextDnsConfigEntry
) -> None:
    """Reload the config entry when subentries change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NextDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
