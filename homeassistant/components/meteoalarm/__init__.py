"""The MeteoAlarm integration."""

from dataclasses import dataclass
from typing import Any

from meteoalarmapi import Meteoalert, ServerError, UnexpectedError, WrongCountry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_PROVINCE, PLATFORMS


@dataclass
class MeteoAlarmData:
    """The client, and the alert fetched when the entry was set up."""

    api: Meteoalert
    alert: dict[str, Any]


type MeteoAlarmConfigEntry = ConfigEntry[MeteoAlarmData]


async def async_setup_entry(hass: HomeAssistant, entry: MeteoAlarmConfigEntry) -> None:
    """Set up MeteoAlarm from a config entry."""
    api = Meteoalert(
        entry.data[CONF_COUNTRY], entry.data[CONF_PROVINCE], entry.data[CONF_LANGUAGE]
    )
    try:
        alert = await hass.async_add_executor_job(api.get_alert)
    except (ServerError, UnexpectedError, WrongCountry) as err:
        raise ConfigEntryNotReady(f"Error fetching MeteoAlarm data: {err}") from err

    entry.runtime_data = MeteoAlarmData(api, alert)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: MeteoAlarmConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
