"""The TSUN integration."""

from tsun_local_api import LoggerMetadata, TsunClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_FIRMWARE_VERSION,
    CONF_INVERTER_SN,
    CONF_LOGGER_SN,
    CONF_MAC_ADDRESS,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import TsunDataUpdateCoordinator, get_poll_lock

PLATFORMS = (Platform.SENSOR,)

type TsunConfigEntry = ConfigEntry[TsunDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TsunConfigEntry) -> bool:
    """Set up TSUN from a config entry."""
    metadata = LoggerMetadata(
        logger_sn=entry.data[CONF_LOGGER_SN],
        inverter_serial_number=entry.data.get(CONF_INVERTER_SN),
        firmware_version=entry.data.get(CONF_FIRMWARE_VERSION),
        mac_address=entry.data.get(CONF_MAC_ADDRESS),
    )
    client = TsunClient(
        entry.data[CONF_HOST],
        entry.data[CONF_LOGGER_SN],
        port=entry.data[CONF_PORT],
        metadata=metadata,
    )
    coordinator = TsunDataUpdateCoordinator(
        hass,
        entry,
        client,
        poll_lock=get_poll_lock(hass),
        update_interval=DEFAULT_SCAN_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TsunConfigEntry) -> bool:
    """Unload a TSUN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
