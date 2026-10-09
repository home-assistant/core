"""Support for WaterFurnace geothermal systems."""

import asyncio
import logging

from waterfurnace.waterfurnace import WaterFurnace, WFCredentialError, WFException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.start import async_at_started

from .coordinator import (
    WaterFurnaceCoordinator,
    WaterFurnaceDeviceData,
    WaterFurnaceEnergyCoordinator,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]


type WaterFurnaceConfigEntry = ConfigEntry[dict[str, WaterFurnaceDeviceData]]


async def _async_setup_coordinator(
    hass: HomeAssistant,
    username: str,
    password: str,
    device_index: int,
    entry: WaterFurnaceConfigEntry,
) -> tuple[str, WaterFurnaceDeviceData]:
    """Set up a coordinator for a device."""

    device_client = WaterFurnace(username, password, device=device_index)
    await hass.async_add_executor_job(device_client.login)
    coordinator = WaterFurnaceCoordinator(hass, device_client, entry)
    await coordinator.async_config_entry_first_refresh()

    if device_client.gwid is None:
        raise ConfigEntryNotReady(
            f"Invalid GWID for device at index {device_index}: {device_client.gwid}"
        )

    energy_coordinator = WaterFurnaceEnergyCoordinator(
        hass, device_client, entry, device_client.gwid
    )

    # Defer the first energy refresh until HA has fully started so the
    # potentially large initial backfill doesn't compete with startup I/O.
    async def _async_start_energy(hass: HomeAssistant) -> None:
        await energy_coordinator.async_refresh()

    entry.async_on_unload(async_at_started(hass, _async_start_energy))

    return device_client.gwid, WaterFurnaceDeviceData(
        realtime=coordinator, energy=energy_coordinator
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Set up WaterFurnace from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    client = WaterFurnace(username, password)

    try:
        await hass.async_add_executor_job(client.login)
    except WFCredentialError as err:
        raise ConfigEntryAuthFailed(
            "Authentication failed. Please update your credentials."
        ) from err

    device_count = len(client.devices) if client.devices else 0

    results = await asyncio.gather(
        *[
            _async_setup_coordinator(hass, username, password, index, entry)
            for index in range(device_count)
        ]
    )
    entry.runtime_data = dict(results)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Unload a WaterFurnace config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: WaterFurnaceConfigEntry
) -> bool:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 2:
        # Migrate from gwid-based unique_id to account_id-based unique_id
        client = WaterFurnace(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
        try:
            await hass.async_add_executor_job(client.login)
        except WFCredentialError, WFException:
            _LOGGER.error("Failed to login during migration to account_id")
            return False

        if client.account_id is None:
            _LOGGER.error("Account ID is invalid during migration")
            return False

        hass.config_entries.async_update_entry(
            entry, unique_id=str(client.account_id), minor_version=2
        )
        _LOGGER.info("Migrated config entry unique_id to account_id")

    return True
