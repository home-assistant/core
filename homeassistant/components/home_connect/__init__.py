"""Support for BSH Home Connect appliances."""

from __future__ import annotations

import logging
from typing import Any

from aiohomeconnect.client import Client as HomeConnectClient
import aiohttp
import jwt

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    issue_registry as ir,
)
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries
from homeassistant.helpers.typing import ConfigType

from .api import AsyncConfigEntryAuth
from .const import DOMAIN, OLD_NEW_UNIQUE_ID_SUFFIX_MAP
from .coordinator import HomeConnectConfigEntry, HomeConnectCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Home Connect component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomeConnectConfigEntry) -> bool:
    """Set up Home Connect from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    config_entry_auth = AsyncConfigEntryAuth(hass, session)
    try:
        await config_entry_auth.async_get_access_token()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    home_connect_client = HomeConnectClient(config_entry_auth)

    coordinator = HomeConnectCoordinator(hass, entry, home_connect_client)
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.runtime_data.start_event_listener()

    entry.async_create_background_task(
        hass,
        coordinator.async_refresh(),
        f"home_connect-initial-full-refresh-{entry.entry_id}",
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> bool:
    """Unload a config entry."""
    issue_registry = ir.async_get(hass)
    issues_to_delete = [
        "deprecated_set_program_and_option_actions",
        "deprecated_command_actions",
    ] + [
        issue_id
        for (issue_domain, issue_id) in issue_registry.issues
        if issue_domain == DOMAIN
        and issue_id.startswith("home_connect_too_many_connected_paired_events")
    ]
    for issue_id in issues_to_delete:
        issue_registry.async_delete(DOMAIN, issue_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        match entry.minor_version:
            case 1:

                @callback
                def update_unique_id(
                    entity_entry: RegistryEntry,
                ) -> dict[str, Any] | None:
                    """Update unique ID of entity entry."""
                    for (
                        old_id_suffix,
                        new_id_suffix,
                    ) in OLD_NEW_UNIQUE_ID_SUFFIX_MAP.items():
                        if entity_entry.unique_id.endswith(f"-{old_id_suffix}"):
                            return {
                                "new_unique_id": entity_entry.unique_id.replace(
                                    old_id_suffix, new_id_suffix
                                )
                            }
                    return None

                await async_migrate_entries(hass, entry.entry_id, update_unique_id)

                hass.config_entries.async_update_entry(entry, minor_version=2)
            case 2:
                hass.config_entries.async_update_entry(
                    entry,
                    minor_version=3,
                    unique_id=jwt.decode(
                        entry.data["token"]["access_token"],
                        options={"verify_signature": False},
                    )["sub"],
                )

    _LOGGER.debug("Migration to version %s successful", entry.version)
    return True
