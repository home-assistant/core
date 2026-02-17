"""DataUpdateCoordinator for AWS S3."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiobotocore.client import AioBaseClient as S3Client
from botocore.exceptions import BotoCoreError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_BUCKET, DOMAIN
from .helpers import async_list_backups_from_s3

SCAN_INTERVAL = timedelta(hours=6)

type S3ConfigEntry = ConfigEntry[S3DataUpdateCoordinator]

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorData:
    """Class to represent sensor data."""

    all_backups_size: int


class S3DataUpdateCoordinator(DataUpdateCoordinator[SensorData]):
    """Class to manage fetching AWS S3 data from single endpoint."""

    config_entry: S3ConfigEntry
    client: S3Client

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry: S3ConfigEntry,
        client: S3Client,
    ) -> None:
        """Initialize AWS S3 data updater."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self._bucket: str = entry.data[CONF_BUCKET]

    async def _async_update_data(self) -> SensorData:
        """Fetch data from AWS S3."""
        try:
            backups = await async_list_backups_from_s3(self.client, self._bucket)
        except BotoCoreError as error:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="error_fetching_data",
            ) from error

        all_backups_size = sum(b.size for b in backups)
        return SensorData(
            all_backups_size=all_backups_size,
        )
