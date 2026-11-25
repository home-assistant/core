"""The APsystems local API integration."""

from typing import cast

from APsystemsEZ1 import APsystemsEZ1M

from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_DEVICE_TYPE, DEFAULT_PORT, DEVICE_TYPE_EZ1, DEVICE_TYPE_LAKE6
from .coordinator import ApSystemsConfigEntry, ApSystemsData, ApSystemsDataCoordinator
from .lake6.client import Lake6ApiClient
from .lake6.const import LAKE6_DEFAULT_PORT
from .lake6.coordinator import Lake6ConfigEntry, Lake6Coordinator, Lake6RuntimeData

# EZ1 has no select or text platform. The two lists are kept apart so EZ1 does
# not load empty platforms.
EZ1_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

LAKE6_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]


async def async_migrate_entry(hass: HomeAssistant, entry: ApSystemsConfigEntry) -> None:
    """Backfill `device_type` on entries created before Lake support."""
    if entry.version < 2:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_DEVICE_TYPE: DEVICE_TYPE_EZ1},
            version=2,
        )


async def async_setup_entry(hass: HomeAssistant, entry: ApSystemsConfigEntry) -> None:
    """Set up this integration using UI."""
    if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_LAKE6:
        entry.runtime_data = await _async_setup_lake6(hass, entry)
        platforms = LAKE6_PLATFORMS
    else:
        entry.runtime_data = await _async_setup_ez1(hass, entry)
        platforms = EZ1_PLATFORMS
    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_unload_entry(hass: HomeAssistant, entry: ApSystemsConfigEntry) -> None:
    """Unload a config entry."""
    # Branch on the entry data instead of runtime_data: HA deletes runtime_data
    # before unloading, so it is not a reliable fact here.
    platforms = (
        LAKE6_PLATFORMS
        if entry.data.get(CONF_DEVICE_TYPE) == DEVICE_TYPE_LAKE6
        else EZ1_PLATFORMS
    )
    await hass.config_entries.async_unload_platforms_or_raise(entry, platforms)


async def _async_setup_ez1(
    hass: HomeAssistant, entry: ApSystemsConfigEntry
) -> ApSystemsData:
    """Build the EZ1 client and coordinator."""
    api = APsystemsEZ1M(
        ip_address=entry.data[CONF_IP_ADDRESS],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        timeout=8,
        enable_debounce=True,
    )
    coordinator = ApSystemsDataCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    assert entry.unique_id
    return ApSystemsData(coordinator=coordinator, device_id=entry.unique_id)


async def _async_setup_lake6(
    hass: HomeAssistant, entry: ApSystemsConfigEntry
) -> Lake6RuntimeData:
    """Build the Lake_6 client and coordinator."""
    client = Lake6ApiClient(
        host=entry.data[CONF_IP_ADDRESS],
        session=async_get_clientsession(hass),
        port=entry.data.get(CONF_PORT, LAKE6_DEFAULT_PORT),
    )
    coordinator = Lake6Coordinator(hass, cast(Lake6ConfigEntry, entry), client)
    # A failed first refresh becomes ConfigEntryNotReady, which puts the entry
    # into a retry.
    await coordinator.async_config_entry_first_refresh()
    return Lake6RuntimeData(
        coordinator=coordinator,
        device_id=coordinator.device.dev_id,
        device=coordinator.device,
    )
