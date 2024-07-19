"""The GPSD integration."""

from __future__ import annotations

from dataclasses import dataclass

from gps3.agps3threaded import AGPS3mechanism

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GPSDConfigEntry = ConfigEntry[GPSDData]


@dataclass
class GPSDData:
    """GPSD data type."""

    agps_thread: AGPS3mechanism


async def async_setup_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Set up GPSD from a config entry."""
    agps_thread = AGPS3mechanism()
    entry.runtime_data = GPSDData(agps_thread)

    def setup_agps() -> None:
        host = entry.data.get(CONF_HOST)
        port = entry.data.get(CONF_PORT)
        agps_thread.stream_data(host, port)
        agps_thread.run_thread()

    await hass.async_add_executor_job(setup_agps)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GPSDConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        agps_thread = entry.runtime_data.agps_thread
        await hass.async_add_executor_job(
            lambda: lambda: agps_thread.stream_data(
                host=entry.data.get(CONF_HOST),
                port=entry.data.get(CONF_PORT),
                enable=False,
            )
        )

    return unload_ok
