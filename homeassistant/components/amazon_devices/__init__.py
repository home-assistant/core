"""Amazon Devices integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_LOGIN_DATA, DOMAIN
from .coordinator import AmazonDevicesCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Amazon Devices platform."""

    coordinator = AmazonDevicesCoordinator(
        hass,
        entry.data[CONF_COUNTRY],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_LOGIN_DATA],
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: AmazonDevicesCoordinator = hass.data[DOMAIN][entry.entry_id]
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await coordinator.api.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
