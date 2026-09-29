"""The energieleser integration."""

from energieleser import EnergieleserClient

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    EnergieleserConfigEntry,
    EnergieleserCoordinator,
    EnergieleserData,
    EnergieleserFirmwareCoordinator,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]

FIRMWARE_COORDINATOR: HassKey[EnergieleserFirmwareCoordinator] = HassKey(
    f"{DOMAIN}_firmware_coordinator"
)


async def async_setup_entry(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> bool:
    """Set up energieleser from a config entry."""
    client = EnergieleserClient(
        host=entry.data[CONF_HOST],
        session=async_get_clientsession(hass),
    )
    coordinator = EnergieleserCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    if (firmware_coordinator := hass.data.get(FIRMWARE_COORDINATOR)) is None:
        firmware_coordinator = EnergieleserFirmwareCoordinator(hass)
        hass.data[FIRMWARE_COORDINATOR] = firmware_coordinator
        await firmware_coordinator.async_register_shutdown()
        hass.async_create_background_task(
            firmware_coordinator.async_refresh(), f"{DOMAIN} firmware check"
        )
    entry.runtime_data = EnergieleserData(
        device_coordinator=coordinator,
        firmware_coordinator=firmware_coordinator,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> bool:
    """Unload an energieleser config entry."""
    ir.async_delete_issue(hass, DOMAIN, f"pin_locked_{entry.entry_id}")
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and not hass.config_entries.async_loaded_entries(DOMAIN):
        await hass.data[FIRMWARE_COORDINATOR].async_shutdown()
        hass.data.pop(FIRMWARE_COORDINATOR)
    return unload_ok
