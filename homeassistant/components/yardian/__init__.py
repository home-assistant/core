"""The Yardian integration."""

from pyyardian import AsyncYardianClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import config_validation as cv # Add this import
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import YardianConfigEntry, YardianUpdateCoordinator

# Add this line before async_setup
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Yardian integration."""

    async def handle_stop_all(call: ServiceCall) -> None:
        """Service call to stop all irrigation on a specific controller."""
        device_registry = dr.async_get(hass)

        # Get the device_id from the service call target
        target_device_ids = call.data.get("device_id", [])
        if isinstance(target_device_ids, str):
            target_device_ids = [target_device_ids]

        for device_id in target_device_ids:
            device = device_registry.async_get(device_id)
            if not device:
                continue

            # Find the config entry associated with this device
            for entry_id in device.config_entries:
                if entry_id in hass.data.get(DOMAIN, {}):
                    coordinator = hass.data[DOMAIN][entry_id]
                    await coordinator.controller.stop_irrigation()
                    await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "stop_all_irrigation", handle_stop_all)

    return True

async def async_setup_entry(hass: HomeAssistant, entry: YardianConfigEntry) -> bool:
    """Set up Yardian from a config entry."""

    host = entry.data[CONF_HOST]
    # Change from required to option for the Access Token
    #access_token = entry.data[CONF_ACCESS_TOKEN]
    access_token = entry.data.get(CONF_ACCESS_TOKEN, "")

    controller = AsyncYardianClient(async_get_clientsession(hass), host, access_token)
    coordinator = YardianUpdateCoordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Store coordinator in hass.data so the global service can find it by entry_id
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: YardianConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok