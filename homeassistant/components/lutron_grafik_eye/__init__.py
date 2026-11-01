"""The Lutron GRAFIK Eye integration."""

from grafikeye import GrafikEyeController
from grafikeye.exceptions import GrafikEyeAuthenticationError, GrafikEyeConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

PLATFORMS = [Platform.SELECT]

type GrafikEyeConfigEntry = ConfigEntry[GrafikEyeController]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GrafikEyeConfigEntry,
) -> None:
    """Set up Lutron GRAFIK Eye from a config entry."""
    controller = GrafikEyeController(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        login=entry.data[CONF_PASSWORD],
    )

    try:
        await controller.connect()
    except GrafikEyeAuthenticationError as error:
        raise ConfigEntryAuthFailed from error
    except GrafikEyeConnectionError as error:
        raise ConfigEntryNotReady from error

    entry.runtime_data = controller

    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await controller.disconnect()
        raise


async def async_unload_entry(
    hass: HomeAssistant,
    entry: GrafikEyeConfigEntry,
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.disconnect()
