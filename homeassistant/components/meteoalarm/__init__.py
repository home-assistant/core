"""The MeteoAlarm integration."""

from meteoalarmapi import Meteoalert

from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant

from .const import CONF_PROVINCE, PLATFORMS
from .coordinator import MeteoAlarmConfigEntry, MeteoAlarmCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: MeteoAlarmConfigEntry) -> None:
    """Set up MeteoAlarm from a config entry."""
    api = Meteoalert(
        entry.data[CONF_COUNTRY], entry.data[CONF_PROVINCE], entry.data[CONF_LANGUAGE]
    )
    coordinator = MeteoAlarmCoordinator(hass, entry, api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MeteoAlarmConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
