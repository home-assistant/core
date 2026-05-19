"""The Raspberry Pi integration."""

from homeassistant.components.hassio import HassioNotReadyError, get_os_info
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.hassio import is_hassio


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Raspberry Pi config entry."""
    if not is_hassio(hass):
        # Not running under supervisor, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    try:
        os_info = get_os_info(hass)
    except HassioNotReadyError as err:
        raise ConfigEntryNotReady from err

    board: str | None
    if (board := os_info.get("board")) is None or not board.startswith("rpi"):
        # Not running on a Raspberry Pi, Home Assistant may have been migrated
        hass.async_create_task(hass.config_entries.async_remove(entry.entry_id))
        return False

    await hass.config_entries.flow.async_init(
        "rpi_power", context={"source": "onboarding"}
    )

    return True
