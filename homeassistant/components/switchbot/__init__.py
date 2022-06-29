"""Support for Switchbot devices."""

import switchbot

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SENSOR_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import (
    ATTR_BOT,
    ATTR_CURTAIN,
    COMMON_OPTIONS,
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    CONF_SCAN_TIMEOUT,
    CONF_TIME_BETWEEN_UPDATE_COMMAND,
    DATA_COORDINATOR,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_TIME_BETWEEN_UPDATE_COMMAND,
    DOMAIN,
)
from .coordinator import SwitchbotDataUpdateCoordinator

PLATFORMS_BY_TYPE = {
    ATTR_BOT: [Platform.SWITCH, Platform.SENSOR],
    ATTR_CURTAIN: [Platform.COVER, Platform.BINARY_SENSOR, Platform.SENSOR],
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Switchbot from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    if not entry.options:
        options = {
            CONF_TIME_BETWEEN_UPDATE_COMMAND: DEFAULT_TIME_BETWEEN_UPDATE_COMMAND,
            CONF_RETRY_COUNT: DEFAULT_RETRY_COUNT,
            CONF_RETRY_TIMEOUT: DEFAULT_RETRY_TIMEOUT,
            CONF_SCAN_TIMEOUT: DEFAULT_SCAN_TIMEOUT,
        }

        hass.config_entries.async_update_entry(entry, options=options)

    # Use same coordinator instance for all entities.
    # Uses BTLE advertisement data, all Switchbot devices in range is stored here.
    if DATA_COORDINATOR not in hass.data[DOMAIN]:

        if COMMON_OPTIONS not in hass.data[DOMAIN]:
            hass.data[DOMAIN][COMMON_OPTIONS] = {**entry.options}

        switchbot.DEFAULT_RETRY_TIMEOUT = hass.data[DOMAIN][COMMON_OPTIONS][
            CONF_RETRY_TIMEOUT
        ]

        # Store api in coordinator.
        coordinator = SwitchbotDataUpdateCoordinator(
            hass,
            update_interval=hass.data[DOMAIN][COMMON_OPTIONS][
                CONF_TIME_BETWEEN_UPDATE_COMMAND
            ],
            api=switchbot,
            retry_count=hass.data[DOMAIN][COMMON_OPTIONS][CONF_RETRY_COUNT],
            scan_timeout=hass.data[DOMAIN][COMMON_OPTIONS][CONF_SCAN_TIMEOUT],
        )

        hass.data[DOMAIN][DATA_COORDINATOR] = coordinator

    else:
        coordinator = hass.data[DOMAIN][DATA_COORDINATOR]

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

    sensor_type = entry.data[CONF_SENSOR_TYPE]

    hass.config_entries.async_setup_platforms(entry, PLATFORMS_BY_TYPE[sensor_type])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    sensor_type = entry.data[CONF_SENSOR_TYPE]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS_BY_TYPE[sensor_type]
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        if len(hass.config_entries.async_entries(DOMAIN)) == 0:
            hass.data.pop(DOMAIN)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    # Update entity options stored in hass.
    if {**entry.options} != hass.data[DOMAIN][COMMON_OPTIONS]:
        hass.data[DOMAIN][COMMON_OPTIONS] = {**entry.options}
        hass.data[DOMAIN].pop(DATA_COORDINATOR)

    await hass.config_entries.async_reload(entry.entry_id)
