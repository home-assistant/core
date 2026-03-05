"""The NUT coordinator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aionut import NUTError, NUTLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import PyNUTData

_LOGGER = logging.getLogger(__name__)


@dataclass
class NutRuntimeData:
    """Runtime data definition."""

    coordinator: NutCoordinator
    data: PyNUTData
    unique_id: str
    user_available_commands: set[str]


type NutConfigEntry = ConfigEntry[NutRuntimeData]


class NutCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Coordinator for NUT data."""

    config_entry: NutConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        data: PyNUTData,
        config_entry: NutConfigEntry,
    ) -> None:
        """Initialize NUT coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="NUT resource status",
            update_interval=timedelta(seconds=60),
            always_update=False,
        )
        self._data = data

    async def _async_update_data(self) -> dict[str, str]:
        """Fetch data from NUT."""
        try:
            return await self._data.async_update()
        except NUTLoginError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "err": str(err),
                },
            ) from err
        except NUTError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="data_fetch_error",
                translation_placeholders={
                    "err": str(err),
                },
            ) from err
