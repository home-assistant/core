"""The IntelliFire integration."""
from __future__ import annotations

from intellifire4py import IntellifireAsync, IntellifireControlAsync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER
from .coordinator import IntellifireDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IntelliFire from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.unique_id)

    # Define the API Object
    read_object = IntellifireAsync(entry.data[CONF_HOST])

    ift_control = IntellifireControlAsync(
        fireplace_ip=entry.data[CONF_HOST],
        use_http=(not entry.data[CONF_SSL]),
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    try:
        await ift_control.login(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
        )
    finally:
        await ift_control.close()

    # Define the update coordinator
    coordinator = IntellifireDataUpdateCoordinator(
        hass=hass, read_api=read_object, control_api=ift_control
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if config_entry.version == 1:
        # There is no migration path from v1-2 as we need more data
        LOGGER.warning(
            "Intellifire must be reconfigured - Migration from v1 to v2 not possible"
        )
        return False

    return False
