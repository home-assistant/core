"""The solmate_mocks integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
DOMAIN = "solmate_mocks"
MOCK_TESLA_DEVICE_ID = "mock_tesla_ble_device"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Solmate Mocks component."""
    _LOGGER.info("Setting up Solmate Mocks component")

    # Create a config entry if one doesn't exist
    if not hass.config_entries.async_entries(DOMAIN):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data={},
        )
        if result.type != "create_entry":
            return False
    else:
        result = hass.config_entries.async_entries(DOMAIN)[0]

    # register mock Tesla BLE device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=result.entry_id,
        identifiers={(DOMAIN, MOCK_TESLA_DEVICE_ID)},
        name="Mock Tesla BLE Device",
        manufacturer="espressif",
        model="esp32",
        sw_version="1.0",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up solmate_mocks from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
