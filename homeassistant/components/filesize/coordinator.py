"""Coordinator for monitoring the size of a file."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
import pathlib

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class FileSizeCoordinator(DataUpdateCoordinator[dict[str, int | float | datetime]]):
    """Filesize coordinator."""

    path: pathlib.Path

    def __init__(self, hass: HomeAssistant, unresolved_path: str) -> None:
        """Initialize filesize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
            always_update=False,
        )
        self._unresolved_path = unresolved_path

    def _get_full_path(self) -> pathlib.Path:
        """Check if path is valid, allowed and return full path."""
        path = self._unresolved_path
        get_path = pathlib.Path(path)
        if not self.hass.config.is_allowed_path(path):
            raise UpdateFailed(f"Filepath {path} is not valid or allowed")

        if not get_path.exists() or not get_path.is_file():
            raise UpdateFailed(f"Can not access file {path}")

        return get_path.absolute()

    def _update(self) -> os.stat_result:
        """Fetch file information."""
        if not hasattr(self, "path"):
            self.path = self._get_full_path()

        try:
            return self.path.stat()
        except OSError as error:
            raise UpdateFailed(f"Can not retrieve file statistics {error}") from error

    async def _async_update_data(self) -> dict[str, float | int | datetime]:
        """Fetch file information."""
        statinfo = await self.hass.async_add_executor_job(self._update)
        size = statinfo.st_size
        last_updated = dt_util.utc_from_timestamp(statinfo.st_mtime)

        _LOGGER.debug("size %s, last updated %s", size, last_updated)
        data: dict[str, int | float | datetime] = {
            "file": round(size / 1e6, 2),
            "bytes": size,
            "last_updated": last_updated,
        }

        return data
