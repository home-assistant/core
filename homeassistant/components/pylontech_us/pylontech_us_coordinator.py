"""The pylontech_us coordinator."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
from pylontech import PylontechStack

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


class PylontechUsCoordinator(DataUpdateCoordinator):
    """Coordinator class to collect data from battery."""

    def __init__(
        self, hass: HomeAssistant, port: str, baud: int, battery_count: int
    ) -> None:
        """Pylontech setup."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._port = port
        self._baud = baud
        self._battery_count = battery_count
        self._stack = None
        self._last_result = None

    def _connect_stack(self) -> None:
        """Validate the user input allows us to connect.

        Set _stack to None on error
        """
        try:
            self._stack = PylontechStack(
                device=self._port,
                baud=self._baud,
                manualBattcountLimit=self._battery_count,
            )
        except Exception as exc:  # pylint: disable=broad-except
            print("Pylontech connect failed, might be in standby: ", exc)
            self._stack = None

    def update(self):
        """Create callable for call from async."""

        if self._stack is None:
            return

        retry = 0
        while retry < 3:
            try:
                self._last_result = self._stack.update()
            except ValueError:
                self._last_result = None
                print("Pylontech retry update, ValueError")
            except Exception as exc:  # pylint: disable=broad-except
                self._last_result = None
                print("Pylontech retry update, Exception ", exc)
            retry = retry + 1

    async def async_config_entry_first_refresh(self):
        """Refresh on first start."""
        retry = 0
        if self._stack is None:
            return

        while retry < 3:
            try:
                self._last_result = self._stack.update()
            except ValueError:
                print("Pylontech retry update, ValueError")
                self._last_result = None
            except Exception as exc:  # pylint: disable=broad-except
                print("Pylontech retry update, Exception ", exc)
                self._last_result = None
            retry = retry + 1

        if self._last_result is not None:
            return

        ex = ConfigEntryNotReady()
        ex.__cause__ = self.last_exception
        raise ex

    async def _async_update_data(self) -> (Any | None):
        """Fetch data from Battery."""

        if self._stack is None:
            async with async_timeout.timeout(45):
                await self.hass.async_add_executor_job(self._connect_stack)

        async with async_timeout.timeout(45):
            await self.hass.async_add_executor_job(self.update)

        if self._last_result is not None:
            self.last_update_success = True
            return self._stack.pylonData

        self.last_update_success = False
        # raise UpdateFailed("Error communicating with API.")
        return None

    async def async_update_data(self) -> (Any | None):
        """Fetch data from Battery."""

        if self._stack is None:
            async with async_timeout.timeout(45):
                await self.hass.async_add_executor_job(self._connect_stack)

        async with async_timeout.timeout(45):
            await self.hass.async_add_executor_job(self.update)

        if self._last_result is not None:
            self.last_update_success = True
            return self._stack.pylonData

        self.last_update_success = False
        # raise UpdateFailed("Error communicating with API.")
        return None

    def get_result(self):
        """Return result dict from last poll."""
        return self._last_result
