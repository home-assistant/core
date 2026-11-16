"""The my-PV integration for Home Assistant."""

from my_pv import MyPVLocalDevice
from my_pv.exceptions import MyPVAuthenticationError, MyPVDeviceNotSupportedError

from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import MyPVConfigEntry, MyPVCoordinator

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
    Platform.WATER_HEATER,
]


async def async_setup_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> None:
    """Set up my-PV from a config entry."""

    device = MyPVLocalDevice(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PASSWORD),
        session=async_get_clientsession(hass),
    )

    try:
        if not await device.connect():
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            )
    except MyPVAuthenticationError as exc:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_error",
        ) from exc
    except MyPVDeviceNotSupportedError as exc:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_device",
        ) from exc

    coordinator = MyPVCoordinator(hass, entry, device)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady, ConfigEntryAuthFailed:
        await coordinator.async_disconnect()
        raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MyPVConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await entry.runtime_data.async_disconnect()
