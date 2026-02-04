"""Update coordinators for Yardian."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import datetime
import logging

from pyyardian import AsyncYardianClient, NetworkException, NotAuthorizedException
from pyyardian.typing import OperationInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(seconds=30)


@dataclass(slots=True)
class YardianZone:
    """Normalized metadata for a Yardian irrigation zone."""

    name: str
    is_enabled: bool


@dataclass
class YardianCoordinatorData:
    """Combined device state for Yardian."""

    zones: list[YardianZone]
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
        _LOGGER.debug(
            "Fetching Yardian device state for %s (controller=%s)",
            self._name,
            type(self.controller).__name__,
        )
        try:
            async with asyncio.timeout(10):
                # Fetch device state and operation info; specific exceptions are
                # handled by the outer block to avoid double-logging.
                dev_state = await self.controller.fetch_device_state()
                oper_info = await self.controller.fetch_oper_info()

        except TimeoutError as e:
            raise UpdateFailed("Timeout communicating with device") from e
        except NotAuthorizedException as e:
            raise ConfigEntryError("Invalid access token") from e
        except NetworkException as e:
            raise UpdateFailed("Failed to communicate with device") from e
        except Exception as e:  # safety net for tests to surface failure reason
            _LOGGER.exception("Unexpected error while fetching Yardian data")
            raise UpdateFailed(f"Unexpected error: {type(e).__name__}: {e}") from e

        _LOGGER.debug(
            "Fetched Yardian data: zones=%s active=%s oper_keys=%s",
            len(dev_state.zones),
            len(dev_state.active_zones),
            list(oper_info.keys()),
        )

        return YardianCoordinatorData(
            zones=[
                YardianZone(
                    name=str(zone_info[0]),
                    is_enabled=zone_info[1] == 1,
                )
                for zone_info in dev_state.zones
            ],
            active_zones=set(dev_state.active_zones),
            oper_info=oper_info,
        )
