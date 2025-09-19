"""Update coordinators for Yardian."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
import logging
from typing import Any

from pyyardian import AsyncYardianClient, NetworkException, NotAuthorizedException
from pyyardian.typing import OperationInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)


@dataclass
class YardianCoordinatorData:
    """Combined device state for Yardian."""

    zones: list[list[Any]]
    active_zones: set[int]
    oper_info: OperationInfo


class YardianUpdateCoordinator(DataUpdateCoordinator[YardianCoordinatorData]):
    """Coordinator for Yardian API calls."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        controller: AsyncYardianClient,
    ) -> None:
        """Initialize Yardian API communication."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )

        self.controller = controller
        self.yid = entry.data["yid"]
        self._name = entry.title
        self._model = entry.data["model"]
        self._serial = entry.data.get("serialNumber")

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            name=self._name,
            identifiers={(DOMAIN, self.yid)},
            manufacturer=MANUFACTURER,
            model=self._model,
            serial_number=self._serial,
        )

    async def _async_update_data(self) -> YardianCoordinatorData:
        """Fetch data from Yardian device."""
        try:
            async with asyncio.timeout(10):
                _LOGGER.debug(
                    "Fetching Yardian device state for %s (controller=%s)",
                    self._name,
                    type(self.controller).__name__,
                )
                # Fetch device state and operation info; specific exceptions are
                # handled by the outer block to avoid double-logging.
                dev_state = await self.controller.fetch_device_state()
                oper_info = await self.controller.fetch_oper_info()

        except TimeoutError as e:
            raise UpdateFailed("Timeout communicating with device") from e
        except NotAuthorizedException as e:
            # Trigger reauth flow according to HA best practices
            raise ConfigEntryAuthFailed("Invalid access token") from e
        except NetworkException as e:
            raise UpdateFailed("Failed to communicate with device") from e

        oper_keys = list(oper_info.keys()) if hasattr(oper_info, "keys") else []
        _LOGGER.debug(
            "Fetched Yardian data: zones=%s active=%s oper_keys=%s",
            len(getattr(dev_state, "zones", [])),
            len(getattr(dev_state, "active_zones", [])),
            oper_keys,
        )
        return YardianCoordinatorData(
            zones=dev_state.zones,
            active_zones=dev_state.active_zones,
            oper_info=oper_info,
        )
