"""The my-PV integration for Home Assistant."""

from datetime import timedelta
import logging

from my_pv import MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MyPVCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
]

type MyPVConfigEntry = ConfigEntry[MyPVCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> bool:
    """Set up my-PV from a config entry."""

    update_interval = timedelta(seconds=5)
    device = await MyPVLocalDevice(entry.data[CONF_HOST], entry.data.get(CONF_PASSWORD))

    try:
        if not await device.connect():
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"uri": device.uri},
            )
    except MyPVAuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except MyPVConnectionError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
            translation_placeholders={"uri": device.uri},
        ) from exc

    # Setup coordinator
    coordinator = MyPVCoordinator(hass, entry, device, update_interval)

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: MyPVCoordinator = entry.runtime_data
    await coordinator.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
