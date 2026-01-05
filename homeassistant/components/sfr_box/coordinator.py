"""SFR Box coordinator."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError
from sfrbox_api.models import DslInfo, FtthInfo, SystemInfo, WanInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_SCAN_INTERVAL = timedelta(minutes=1)

type SFRConfigEntry = ConfigEntry[SFRRuntimeData]


@dataclass
class SFRRuntimeData:
    """Runtime data for SFR Box."""

    box: SFRBox
    dsl: SFRDataUpdateCoordinator[DslInfo]
    ftth: SFRDataUpdateCoordinator[FtthInfo]
    system: SFRDataUpdateCoordinator[SystemInfo]
    wan: SFRDataUpdateCoordinator[WanInfo]


class SFRDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Coordinator to manage data updates."""

    config_entry: SFRConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SFRConfigEntry,
        box: SFRBox,
        name: str,
        method: Callable[[SFRBox], Coroutine[Any, Any, _DataT | None]],
    ) -> None:
        """Initialize coordinator."""
        self.box = box
        self._method = method
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> _DataT:
        """Update data."""
        try:
            if data := await self._method(self.box):
                return data
        except SFRBoxError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unknown_error",
                translation_placeholders={"error": str(err)},
            ) from err
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="no_data",
        )
