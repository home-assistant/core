"""The my-PV integration for Home Assistant."""

from my_pv import MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> bool:
    """Set up my-PV from a config entry."""

    device = MyPVLocalDevice(entry.data[CONF_HOST], entry.data.get(CONF_PASSWORD))

    try:
        if not await device.connect():
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
    except MyPVAuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc

    coordinator = MyPVCoordinator(hass, entry, device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady, ConfigEntryAuthFailed:
        await coordinator.async_disconnect()
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.async_disconnect()

    return unload_ok
