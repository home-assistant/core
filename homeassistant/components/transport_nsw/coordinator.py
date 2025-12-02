"""DataUpdateCoordinator for Transport NSW integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, NoReturn

from TransportNSW import TransportNSW

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import ATTR_MODE, CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_DELAY,
    ATTR_DESTINATION,
    ATTR_DUE_IN,
    ATTR_REAL_TIME,
    ATTR_ROUTE,
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


def _raise_update_failed(message: str, exc: Exception | None = None) -> NoReturn:
    """Raise UpdateFailed with the given message."""
    if exc:
        raise UpdateFailed(message) from exc
    raise UpdateFailed(message)


def _get_value(value):
    """Replace the API response 'n/a' value with None."""
    return None if (value is None or value == "n/a") else value


class TransportNSWCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Transport NSW data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry | None = None,
    ) -> None:
        """Initialize the coordinator."""
        self.config_entry = config_entry
        self.subentry = subentry
        self._load_configuration()

        self.transport_nsw = TransportNSW()

        name = self._get_coordinator_name()
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"Transport NSW {name}",
            update_interval=SCAN_INTERVAL,
            config_entry=config_entry,
        )

    def _load_configuration(self) -> None:
        """Load configuration from config entry and subentry."""
        if self.config_entry is None:
            raise ValueError("Config entry is required")

        self.api_key = self.config_entry.data[CONF_API_KEY]

        if self.subentry:
            # New subentry mode
            self.stop_id = self.subentry.data[CONF_STOP_ID]
            self.route = self.subentry.data.get(CONF_ROUTE, "")
            self.destination = self.subentry.data.get(CONF_DESTINATION, "")
        else:
            # Legacy mode
            self.stop_id = self.config_entry.data[CONF_STOP_ID]
            self.route = self.config_entry.options.get(CONF_ROUTE, "")
            self.destination = self.config_entry.options.get(CONF_DESTINATION, "")

    def _get_coordinator_name(self) -> str:
        """Get the coordinator name based on configuration."""
        if self.config_entry is None:
            return DEFAULT_NAME

        if self.subentry:
            return self.subentry.title or f"Stop {self.stop_id}"
        return self.config_entry.data.get("name", DEFAULT_NAME)

    async def async_update_config(
        self, config_entry: ConfigEntry, subentry: ConfigSubentry | None = None
    ) -> None:
        """Update coordinator configuration and trigger refresh."""
        self.config_entry = config_entry
        self.subentry = subentry
        self._load_configuration()

        # Update coordinator name if needed
        new_name = self._get_coordinator_name()
        self.name = f"Transport NSW {new_name}"

        # Trigger immediate refresh with new configuration
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Transport NSW."""
        try:
            data = await self.hass.async_add_executor_job(
                self.transport_nsw.get_departures,
                self.stop_id,
                self.route,
                self.destination,
                self.api_key,
            )

            if data is None:
                _raise_update_failed("No data returned from Transport NSW API")

            return {
                ATTR_ROUTE: _get_value(data.get("route")),
                ATTR_DUE_IN: _get_value(data.get("due")),
                ATTR_DELAY: _get_value(data.get("delay")),
                ATTR_REAL_TIME: _get_value(data.get("real_time")),
                ATTR_DESTINATION: _get_value(data.get("destination")),
                ATTR_MODE: _get_value(data.get("mode")),
            }
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            _raise_update_failed(
                f"Error communicating with Transport NSW API: {exc}", exc
            )
