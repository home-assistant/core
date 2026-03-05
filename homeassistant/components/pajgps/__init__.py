import logging

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import PajGpsCoordinator
from .const import DOMAIN
from .config_flow import _validate_credentials

type PajGpsConfigEntry = ConfigEntry[PajGpsCoordinator]

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: PajGpsConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    error_key = await _validate_credentials(entry.data["email"], entry.data["password"])
    if error_key == "cannot_connect":
        raise ConfigEntryNotReady("Unable to reach the PAJ GPS API.")
    if error_key == "invalid_auth":
        raise ConfigEntryNotReady("Invalid PAJ GPS credentials.")

    pajgps_coordinator = PajGpsCoordinator(hass, dict(entry.data), async_get_clientsession(hass))
    try:
        await pajgps_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        raise
    except Exception as exc:
        raise ConfigEntryNotReady(f"Failed to connect to PAJ GPS: {exc}") from exc

    entry.runtime_data = pajgps_coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_remove_config_entry_device(
    hass: core.HomeAssistant, config_entry: PajGpsConfigEntry, device_entry
) -> bool:
    """Remove a device from the integration."""
    return True


async def _async_update_listener(hass: HomeAssistant, config_entry: PajGpsConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: PajGpsConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_shutdown()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)