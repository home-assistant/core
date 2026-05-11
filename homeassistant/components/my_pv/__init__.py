"""The my-PV integration for Home Assistant."""

import logging

from my_pv import MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVConnectionError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> bool:
    """Set up my-PV from a config entry."""

    device = await MyPVLocalDevice(entry.data[CONF_HOST], entry.data.get(CONF_PASSWORD))

    try:
        if not await device.connect():
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
    except MyPVAuthenticationError as exc:
        raise ConfigEntryAuthFailed from exc
    except MyPVConnectionError as exc:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from exc

    # Setup coordinator
    coordinator = MyPVCoordinator(hass, entry, device)

    try:
        # Fetch initial data so we have data when entities subscribe
        await coordinator.async_config_entry_first_refresh()

        entry.runtime_data = coordinator

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await coordinator.async_disconnect()
        raise

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
