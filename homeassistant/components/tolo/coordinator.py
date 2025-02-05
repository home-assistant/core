"""Component to control TOLO Sauna/Steam Bath."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import NamedTuple

from tololib import ToloClient, ToloSettings, ToloStatus

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import CONF_EXPERT
from .const import (
    CONF_RETRY_COUNT,
    CONF_RETRY_TIMEOUT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_RETRY_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class ToloSaunaData(NamedTuple):
    """Compound class for reflecting full state (status and info) of a TOLO Sauna."""

    status: ToloStatus
    settings: ToloSettings


class ToloSaunaUpdateCoordinator(DataUpdateCoordinator[ToloSaunaData]):
    """DataUpdateCoordinator for TOLO Sauna."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize ToloSaunaUpdateCoordinator."""
        self.client = ToloClient(
            address=entry.data[CONF_HOST],
            retry_timeout=entry.data[CONF_EXPERT].get(
                CONF_RETRY_TIMEOUT, DEFAULT_RETRY_TIMEOUT
            ),
            retry_count=entry.data[CONF_EXPERT].get(
                CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT
            ),
        )
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=f"{entry.title} ({entry.data[CONF_HOST]}) Data Update Coordinator",
            update_interval=timedelta(seconds=5),
        )

    async def _async_update_data(self) -> ToloSaunaData:
        return await self.hass.async_add_executor_job(self._get_tolo_sauna_data)

    def _get_tolo_sauna_data(self) -> ToloSaunaData:
        try:
            status = self.client.get_status()
            settings = self.client.get_settings()
        except TimeoutError as error:
            raise UpdateFailed("communication timeout") from error
        return ToloSaunaData(status, settings)
