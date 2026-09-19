"""ISEO Argo BLE Lock — Home Assistant integration."""

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import IseoConfigEntry, IseoCoordinator, async_build_client

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Set up ISEO Argo BLE Lock from a config entry."""
    address = entry.data[CONF_ADDRESS]
    ble_device = async_ble_device_from_address(hass, address, connectable=True)
    if ble_device is None:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"address": address},
        )

    client = await async_build_client(hass, entry.data, ble_device)
    coordinator = IseoCoordinator(hass, entry, client)
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IseoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
