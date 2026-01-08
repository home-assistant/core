"""Home Assistant integration for Indevolt device."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from indevolt_api import IndevoltAPI, TimeOutException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = 30


class IndevoltCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for fetching and pushing data to indevolt devices."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the indevolt coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
            config_entry=entry,
        )
        self.config_entry = entry

        # Initialize Indevolt API
        self.api = IndevoltAPI(
            host=entry.data["host"],
            port=entry.data["port"],
            session=async_get_clientsession(hass),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        sn = self.config_entry.data.get("sn", "unknown")
        model = self.config_entry.data.get("device_model", "unknown")

        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer="INDEVOLT",
            name=f"INDEVOLT {model}",
            serial_number=sn,
            model=model,
            sw_version=self.config_entry.data.get("fw_version", "unknown"),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch raw JSON data from the device."""
        try:
            if self.config_entry.data.get("generation", 1) == 1:
                keys = [0, 7101, 1664, 1665, 2108, 1502, 1505, 2101, 2107, 1501, 6000, 6001, 6002, 6105, 6004, 6005, 6006, 6007, 7120, 21028]  # fmt: skip
            else:
                keys = [0, 7101, 142, 6105, 2618, 11009, 2101, 2108, 11010, 2108, 667, 2107, 2104, 2105, 11034, 1502, 6004, 6005, 6006, 6007,           # fmt: skip
                        7120, 11016, 2600, 2612, 6001, 6000, 6002, 1502, 1501, 1532, 1600, 1632, 1664, 1633, 1601, 1665, 1634, 1602, 1666, 1635,        # fmt: skip
                        1603, 1667, 11011, 9008, 9032, 9051, 9070, 9165, 9218, 9000, 9016, 9035, 9054, 9149, 9202, 9012, 9030, 9049, 9068, 9163, 9216,  # fmt: skip
                        9004, 9020, 9039, 9058, 9153, 9206, 9013, 19173, 19174, 19175, 19176, 19177]  # fmt: skip

            data: dict[str, Any] = {}
            for key in keys:
                result = await self.api.fetch_data([key])
                data.update(result)

        except TimeOutException as err:
            _LOGGER.warning("Device update timed out: %s", err)
            raise UpdateFailed(f"Device update timed out: {err}") from err

        except Exception as err:
            _LOGGER.warning("Failed to update device data: %s", err)
            raise UpdateFailed(f"Device update failed: {err}") from err

        else:
            return data

    async def async_push_data(self, key: str, value: Any) -> dict[str, Any]:
        """Push/write data values to given key to device."""
        try:
            result = await self.api.set_data(key, value)

        except TimeOutException:
            _LOGGER.warning("Device timed out during data push for sensor %s:", key)
            raise

        except Exception:
            _LOGGER.exception("Failed to push data to device for sensor %s", key)
            raise

        else:
            _LOGGER.info("Data pushed to device %s: %s", key, value)
            _LOGGER.debug("Result of push: %s", str(result))
            return result
