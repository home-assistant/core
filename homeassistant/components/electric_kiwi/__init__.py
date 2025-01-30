"""The Electric Kiwi integration."""

from __future__ import annotations

import aiohttp
from electrickiwi_api import ElectricKiwiApi
from electrickiwi_api.exceptions import ApiException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

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

        ek_session = await ek_api.get_active_session()
        unique_id = str(ek_session.data.customer_number)
        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, minor_version=2
        )

    return True
