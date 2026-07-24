"""Coordinators for the PrusaLink integration."""

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
import logging
from time import monotonic
from typing import Any, TypeVar, override

from httpx import ConnectError
from pyprusalink import (
    JobInfo,
    LegacyPrinterStatus,
    PrinterInfo,
    PrinterStatus,
    PrintFileMetadata,
    PrusaLink,
    VersionInfo,
)
from pyprusalink.file_metadata import parse_metadata_mapping
from pyprusalink.types import InvalidAuth, JobFilePrint, PrinterState, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Allow automations using homeassistant.update_entity to collect
# rapidly-changing metrics.
_MINIMUM_REFRESH_INTERVAL = 1.0

# Job is the only coordinator whose payload can be None — pyprusalink's
# get_job() returns None on HTTP 204 when no job is running. The other
# endpoints always return data or raise on failure. Using `bound=` rather
# than constraint members so `JobInfo | None` fits without forcing a union
# into the constraint list.
T = TypeVar(
    "T",
    bound=PrinterStatus
    | LegacyPrinterStatus
    | JobInfo
    | None
    | PrintFileMetadata
    | PrinterInfo
    | VersionInfo,
)


type PrusaLinkConfigEntry = ConfigEntry[dict[str, PrusaLinkUpdateCoordinator]]


class PrusaLinkUpdateCoordinator(DataUpdateCoordinator[T], ABC):
    """Update coordinator for the printer."""

    config_entry: PrusaLinkConfigEntry
    expect_change_until = 0.0

    def __init__(
        self, hass: HomeAssistant, config_entry: PrusaLinkConfigEntry, api: PrusaLink
    ) -> None:
        """Initialize the update coordinator."""
        self.api = api

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._get_update_interval(None),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=_MINIMUM_REFRESH_INTERVAL, immediate=True
            ),
        )

    @override
    async def _async_update_data(self) -> T:
        """Update the data."""
        try:
            async with asyncio.timeout(5):
                data = await self._fetch_data()
        except InvalidAuth:
            raise UpdateFailed("Invalid authentication") from None
        except PrusaLinkError as err:
            raise UpdateFailed(str(err)) from err
        except (TimeoutError, ConnectError) as err:
            raise UpdateFailed("Cannot connect") from err

        self.update_interval = self._get_update_interval(data)
        return data

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError

    @callback
    def expect_change(self) -> None:
        """Expect a change."""
        self.expect_change_until = monotonic() + 30

    def _get_update_interval(self, data: T | None) -> timedelta:
        """Get new update interval.

        `data` is unused by the base implementation today, but kept on the
        signature so subclasses can override based on payload state — e.g. a
        future transfer coordinator that polls faster while a transfer is
        active. The base class is called once from `__init__` with `None`
        before the first fetch, hence `T | None`.
        """
        if self.expect_change_until > monotonic():
            return timedelta(seconds=5)

        return timedelta(seconds=30)


class StatusCoordinator(PrusaLinkUpdateCoordinator[PrinterStatus]):
    """Printer update coordinator."""

    @override
    async def _fetch_data(self) -> PrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_status()


class LegacyStatusCoordinator(PrusaLinkUpdateCoordinator[LegacyPrinterStatus]):
    """Printer legacy update coordinator."""

    @override
    async def _fetch_data(self) -> LegacyPrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_legacy_printer()


class JobUpdateCoordinator(PrusaLinkUpdateCoordinator[JobInfo | None]):
    """Job update coordinator.

    The job endpoint returns nothing (HTTP 204) when no job is running, so
    `data` can legitimately be `None` here. Entity code that reads from this
    coordinator's data must be `None`-aware.
    """

    @override
    async def _fetch_data(self) -> JobInfo | None:
        """Fetch the printer data."""
        return await self.api.get_job()


class FileMetadataUpdateCoordinator(
    PrusaLinkUpdateCoordinator[PrintFileMetadata | None]
):
    """Print file metadata update coordinator."""

    _cache_key: tuple[str, int | None, int | None] | None = None
    _cache_data: PrintFileMetadata | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PrusaLinkConfigEntry,
        api: PrusaLink,
        job_coordinator: JobUpdateCoordinator,
    ) -> None:
        """Initialize the file metadata update coordinator."""
        self.job_coordinator = job_coordinator
        super().__init__(hass, config_entry, api)

    @callback
    @override
    def async_add_listener(
        self, update_callback: CALLBACK_TYPE, context: Any = None
    ) -> CALLBACK_TYPE:
        """Listen for data updates and fetch metadata when first needed."""
        had_listeners = bool(self._listeners)
        remove_listener = super().async_add_listener(update_callback, context)

        if not had_listeners and self.data is None:
            self.config_entry.async_create_background_task(
                self.hass,
                self.async_request_refresh(),
                "prusalink fetch file metadata",
            )

        return remove_listener

    @callback
    def has_listeners(self) -> bool:
        """Return if any enabled entity is listening for metadata updates."""
        return bool(self._listeners)

    @override
    async def _async_update_data(self) -> PrintFileMetadata | None:
        """Update the file metadata without blocking integration setup."""
        try:
            async with asyncio.timeout(30):
                data = await self._fetch_data()
        except (PrusaLinkError, TimeoutError, ConnectError) as err:
            _LOGGER.debug("Could not fetch PrusaLink file metadata: %s", err)
            data = None

        self.update_interval = self._get_update_interval(data)
        return data

    @override
    async def _fetch_data(self) -> PrintFileMetadata | None:
        """Fetch metadata for the current print file."""
        job = self.job_coordinator.data

        if (
            job is None
            or job.get("state") == PrinterState.IDLE.value
            or (job_file := job.get("file")) is None
        ):
            self._cache_key = None
            self._cache_data = None
            return None

        if (metadata := job_file.get("meta")) is not None:
            return parse_metadata_mapping(metadata)

        download_path = _download_path(job_file)
        cache_key = (download_path, job_file.get("size"), job_file.get("m_timestamp"))
        if cache_key == self._cache_key:
            return self._cache_data

        self._cache_key = cache_key
        self._cache_data = None

        try:
            self._cache_data = await self.api.get_file_metadata(download_path)
        except PrusaLinkError as err:
            _LOGGER.debug("Could not fetch PrusaLink file metadata: %s", err)

        return self._cache_data


def _download_path(job_file: JobFilePrint) -> str:
    """Get the path that can be used to download a print file."""
    if (refs := job_file.get("refs")) is not None and (
        download_path := refs.get("download")
    ) is not None:
        return download_path

    path = job_file["path"]
    name = job_file["name"]
    return f"{path.rstrip('/')}/{name}"


class InfoUpdateCoordinator(PrusaLinkUpdateCoordinator[PrinterInfo]):
    """Info update coordinator."""

    @override
    async def _fetch_data(self) -> PrinterInfo:
        """Fetch the printer data."""
        return await self.api.get_info()


class VersionUpdateCoordinator(PrusaLinkUpdateCoordinator[VersionInfo]):
    """Version update coordinator."""

    @override
    async def _fetch_data(self) -> VersionInfo:
        """Fetch the version data."""
        return await self.api.get_version()
