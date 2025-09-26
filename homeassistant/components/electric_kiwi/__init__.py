"""The Electric Kiwi integration."""

from __future__ import annotations

import aiohttp
from electrickiwi_api import ElectricKiwiApi
from electrickiwi_api.exceptions import ApiException, AuthException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    entity_registry as er,
)

from . import api
from .coordinator import (
    ElectricKiwiAccountDataCoordinator,
    ElectricKiwiConfigEntry,
    ElectricKiwiHOPDataCoordinator,
    ElectricKiwiRuntimeData,
)

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: ElectricKiwiConfigEntry
) -> bool:
    """Set up Electric Kiwi from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    ek_api = ElectricKiwiApi(
        api.ConfigEntryElectricKiwiAuth(
            aiohttp_client.async_get_clientsession(hass), session
        )
    )
    hop_coordinator = ElectricKiwiHOPDataCoordinator(hass, entry, ek_api)
    account_coordinator = ElectricKiwiAccountDataCoordinator(hass, entry, ek_api)

    try:
        await ek_api.set_active_session()
        await hop_coordinator.async_config_entry_first_refresh()
        await account_coordinator.async_config_entry_first_refresh()
    except AuthException as err:
        raise ConfigEntryAuthFailed from err
    except ApiException as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = ElectricKiwiRuntimeData(
        hop=hop_coordinator, account=account_coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ElectricKiwiConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ElectricKiwiConfigEntry
) -> bool:
    """Migrate old entry."""
    if config_entry.version == 1 and config_entry.minor_version == 1:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, config_entry
            )
        )

        session = config_entry_oauth2_flow.OAuth2Session(
            hass, config_entry, implementation
        )

        ek_api = ElectricKiwiApi(
            api.ConfigEntryElectricKiwiAuth(
                aiohttp_client.async_get_clientsession(hass), session
            )
        )
        try:
            await ek_api.set_active_session()
            connection_details = await ek_api.get_connection_details()
        except AuthException:
            config_entry.async_start_reauth(hass)
            return False
        except ApiException:
            return False
        unique_id = str(ek_api.customer_number)
        identifier = ek_api.electricity.identifier
        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, minor_version=2
        )
        entity_registry = er.async_get(hass)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry_id=config_entry.entry_id
        )

        for entity in entity_entries:
            assert entity.config_entry_id
            entity_registry.async_update_entity(
                entity.entity_id,
                new_unique_id=entity.unique_id.replace(
                    f"{unique_id}_{connection_details.id}", f"{unique_id}_{identifier}"
                ),
            )

    return True
