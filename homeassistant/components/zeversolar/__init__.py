"""Local access to the zeversolar inverter integration."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging

from zeversolarlocal import api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt

from .const import COORDINATOR, DOMAIN

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


class DayTracker:
    """Daytracker class."""

    _old: int | None = None

    @staticmethod
    def is_new_day(current: datetime) -> bool:
        """Check if a new day has arrived."""
        _old = DayTracker._old
        DayTracker._old = current.day

        if _old is None:
            return False

        return not _old == DayTracker._old


class ErrorDurationTracker:
    """Track the duration of all timeouts that occur in sequence.

    Many times a ZeverTimeout is not an error. Most of times the reason
    is that the inverter is shut down due to lack of solar power.
    """

    def __init__(self) -> None:
        """Init."""
        self._last_occurence: datetime | None = None

    def get_error_duration(self, current: datetime) -> int:
        """Return the duration of all errors that have occurred in sequence.

        Calling the error_duration assumes there was an error.
        """

        if self._last_occurence is None:
            _LOGGER.debug("No previous error recorded. Setting to %s", current)
            self._last_occurence = current
            return 0

        value = int((current - self._last_occurence).total_seconds() / 3600)
        _LOGGER.debug("Error duration: %s", value)
        return value

    def reset(self) -> None:
        """Reset the first occurrence of an error to None.

        As a result timing will start from zero.
        """
        self._last_occurence = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Local access to the zeversolar inverter from a config entry."""

    zever_url = entry.data[CONF_URL]
    error_duration_tracker = ErrorDurationTracker()

    async def async_update_data() -> api.SolarData:
        """Get solar data from the zever solar inverter."""
        _LOGGER.debug("Updating zeversolar data")
        now = dt.now()

        new_day = DayTracker.is_new_day(now)
        try:
            # not using a timeout here. Timeout is managed by the
            # zeversolarlocal package itself as it is a vital part of the
            # working of the package.
            result = await api.solardata(zever_url, timeout=2)
        except api.ZeverTimeout as err:
            error_duration = error_duration_tracker.get_error_duration(now)
            if error_duration > 26:
                _LOGGER.debug("Errors occurring for more than 24 hours")
                raise UpdateFailed(err) from err
            if new_day:
                _LOGGER.debug("A new day is born! Resetting solar data")
                return api.SolarData(0, 0)
            _LOGGER.debug("A timeout has occurred, but is not considered an error")
            # assuming the inverter is switched off during lack of sun.
            old_data = coordinator.data
            return api.SolarData(old_data.daily_energy, current_power=0)
        except api.ZeverError as err:
            _LOGGER.debug("Unknown response returned. Re-using old data %s", err)
            return coordinator.data
        else:
            error_duration_tracker.reset()
            return result

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="zeversolar",
        update_method=async_update_data,
        update_interval=timedelta(seconds=15),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
