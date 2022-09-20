"""The pylontech_us integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
from pylontech import PylontechStack

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

# from typing_extensions import Self


PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

# currently needs to be run with:
# pip install git+https://github.com/danielschramm/pylontech-python.git@url_issues


class PylontechCoordinator(DataUpdateCoordinator):
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
        self._stack = PylontechStack(
            device=port, baud=baud, manualBattcountLimit=battery_count
        )
        self._last_result = None

    def update(self):
        """Create callable for call from async."""
        retry = 0
        while retry < 3:
            try:
                self._stack.update()
            except ValueError:
                print("Pylontech retry update, ValueError")
            except Exception as exc:  # pylint: disable=broad-except
                print("Pylontech retry update, Exception ", exc)
            retry = retry + 1

    async def async_config_entry_first_refresh(self):
        """Refresh on first start."""
        retry = 0
        while retry < 3:
            try:
                self._last_result = self._stack.update()
            except ValueError:
                print("Pylontech retry update, ValueError")
            except Exception as exc:  # pylint: disable=broad-except
                print("Pylontech retry update, Exception ", exc)
            retry = retry + 1

    async def _async_update_data(self) -> (Any | None):
        """Fetch data from Battery."""
        self.last_update_success = True
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(45):
            await self.hass.async_add_executor_job(self.update)
            return self._stack.pylonData
        # except TypeError as err:
        #    print('TypeError')
        # except:
        #    e = sys.exc_info()[0]
        #    print( "Error: %s" % e )
        #    print('ignore exception')
        # raise UpdateFailed(f"Error communicating with API.")

        # self._lastResult = await self._stack.update()

    def get_result(self):
        """Return result dict from last poll."""
        return self._last_result


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up pylontech_us from a config entry."""
    # TOODOO Store an API object for your platforms to access
    # hass.data[DOMAIN][entry.entry_id] = MyApi(...)

    port = config_entry.data["pylontech_us_port"]
    baud = config_entry.data["pylontech_us_baud"]
    battery_count = config_entry.data["pylontech_us_battery_count"]

    coordinator = PylontechCoordinator(
        hass, port=port, baud=baud, battery_count=battery_count
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
