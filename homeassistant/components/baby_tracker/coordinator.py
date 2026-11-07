"""Sync coordinator: keeps the sync engine current and exposes each baby's latest records."""

import asyncio
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, override

import aiohttp
from pybabytracker import (
    AuthenticationError,
    BabyTrackerClient,
    BabyTrackerError,
    Record,
    SyncEngine,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_UUID, DOMAIN, SCAN_INTERVAL, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)

type BabyTrackerConfigEntry = ConfigEntry[BabyTrackerCoordinator]

FEED_TYPES = ("Nursing", "Formula", "Pumped")


@dataclass(frozen=True, slots=True)
class BabyData:
    """One baby's newest record of each kind the sensors show."""

    baby_id: str
    name: str | None
    diaper: Record | None = None
    feed: Record | None = None
    sleep: Record | None = None


@dataclass(frozen=True, slots=True)
class BabyTrackerData:
    """Everything the entities show, compared by value so an unchanged refresh writes nothing."""

    babies: dict[str, BabyData]


def storage_key(entry_id: str) -> str:
    """Return the storage key for an entry's sync state."""
    return f"{DOMAIN}.{entry_id}"


def _newest(records: list[Record]) -> Record | None:
    def key(record: Record) -> tuple[float, float]:
        if TYPE_CHECKING:
            # latest_records only returns records with a time.
            assert record.time is not None
        stamp = record.timestamp.timestamp() if record.timestamp is not None else 0.0
        return (record.time.timestamp(), stamp)

    return max(records, key=key, default=None)


class BabyTrackerCoordinator(DataUpdateCoordinator[BabyTrackerData]):
    """Syncs with the service, saves the engine's state, and rebuilds each baby's latest records."""

    config_entry: BabyTrackerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: BabyTrackerConfigEntry,
        client: BabyTrackerClient,
        session: aiohttp.ClientSession,
    ) -> None:
        """Set up the coordinator for one account."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
            always_update=False,
        )
        self.client = client
        self.session = session
        self._device_uuid: str = entry.data[CONF_DEVICE_UUID]
        self.engine = SyncEngine(self._device_uuid)
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, storage_key(entry.entry_id)
        )
        self._baby_names: dict[str, str | None] = {}
        self.lock = asyncio.Lock()

    @override
    async def _async_setup(self) -> None:
        """Load what was saved, so a restart fetches only what's newer."""
        await self._async_load_engine()

    async def _async_load_engine(self) -> None:
        try:
            saved = await self._store.async_load()
        except HomeAssistantError as err:
            _LOGGER.warning(
                "The saved sync state couldn't be read (%s); loading all history", err
            )
            return
        if saved is None:
            return
        try:
            self.engine = SyncEngine.from_dict(saved, self._device_uuid)
        except (
            KeyError,
            TypeError,
            ValueError,
            AttributeError,
            BabyTrackerError,
        ) as err:
            _LOGGER.warning(
                "The saved sync state couldn't be read (%r); loading all history again",
                err,
            )

    @override
    async def _async_update_data(self) -> BabyTrackerData:
        async with self.lock:
            return await self._async_sync()

    async def _async_sync(self) -> BabyTrackerData:
        before = dict(self.engine.last_seen)
        try:
            await self.engine.sync(self.client)
        except AuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except BabyTrackerError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="sync_failed_update",
                translation_placeholders={"error": str(err)},
            ) from err
        finally:
            # Keep progress even when a later device failed.
            if dict(self.engine.last_seen) != before:
                await self._async_save()
        return self._rebuild()

    async def _async_save(self) -> None:
        """Save the engine state. A failed save is logged, and never hides a sync error."""
        try:
            await self._store.async_save(self.engine.to_dict())
        except Exception:
            _LOGGER.exception(
                "Couldn't save the sync state; it will be saved after the next sync"
            )

    def _snapshot(self) -> BabyTrackerData:
        """Build the data, changing nothing."""
        names = {
            baby_id: name
            for baby_id, name in self._baby_names.items()
            if not self.engine.is_deleted(baby_id)
        }
        for baby_id, baby in self.engine.babies().items():
            if not self.engine.is_deleted(baby_id):
                names[baby_id] = baby.name
        babies: dict[str, BabyData] = {}
        for baby_id, name in names.items():
            latest = self.engine.latest_records(baby_id)
            babies[baby_id] = BabyData(
                baby_id=baby_id,
                name=name,
                diaper=latest.get("Diaper"),
                feed=_newest([latest[kind] for kind in FEED_TYPES if kind in latest]),
                sleep=latest.get("Sleep"),
            )
        return BabyTrackerData(
            babies=babies,
        )

    def _rebuild(self) -> BabyTrackerData:
        """Build the data, then do what a new snapshot calls for.

        Every path that publishes data comes through here. It remembers the babies' names for the
        next snapshot.
        """
        data = self._snapshot()
        self._baby_names = {baby_id: baby.name for baby_id, baby in data.babies.items()}
        return data
