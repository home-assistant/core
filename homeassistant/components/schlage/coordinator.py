"""DataUpdateCoordinator for the Schlage integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from pyschlage import Lock, Schlage
from pyschlage.exceptions import Error as SchlageError, NotAuthorizedError
from pyschlage.log import LockLog

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


@dataclass
class LockData:
    """Container for cached lock data from the Schlage API."""

    lock: Lock
    logs: list[LockLog]


@dataclass
class SchlageData:
    """Container for cached data from the Schlage API."""

    locks: dict[str, LockData]


type SchlageConfigEntry = ConfigEntry[SchlageDataUpdateCoordinator]


class SchlageDataUpdateCoordinator(DataUpdateCoordinator[SchlageData]):
    """The Schlage data update coordinator."""

    config_entry: SchlageConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SchlageConfigEntry,
        username: str,
        api: Schlage,
    ) -> None:
        """Initialize the class."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} ({username})",
            update_interval=UPDATE_INTERVAL,
        )
        self.data = SchlageData(locks={})
        self.api = api
        self.new_locks_callbacks: list[Callable[[dict[str, LockData]], None]] = []
        self.async_add_listener(self._add_remove_locks)

    async def _async_update_data(self) -> SchlageData:
        """Fetch the latest data from the Schlage API."""
        try:
            locks = await self.hass.async_add_executor_job(self.api.locks)
        except NotAuthorizedError as ex:
            raise ConfigEntryAuthFailed from ex
        except SchlageError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="schlage_refresh_failed"
            ) from ex
        lock_data = await asyncio.gather(
            *(
                self.hass.async_add_executor_job(self._get_lock_data, lock)
                for lock in locks
            )
        )
        return SchlageData(locks={ld.lock.device_id: ld for ld in lock_data})

    def _get_lock_data(self, lock: Lock) -> LockData:
        logs: list[LockLog] = []
        previous_lock_data = None
        if self.data and (previous_lock_data := self.data.locks.get(lock.device_id)):
            # Default to the previous data, in case a refresh fails.
            # It's not critical if we don't have the freshest data.
            logs = previous_lock_data.logs
        try:
            logs = lock.logs()
        except NotAuthorizedError as ex:
            raise ConfigEntryAuthFailed from ex
        except SchlageError as ex:
            LOGGER.debug('Failed to read logs for lock "%s": %s', lock.name, ex)

        return LockData(lock=lock, logs=logs)

    @callback
    def _add_remove_locks(self) -> None:
        """Add newly discovered locks and remove nonexistent locks."""
        device_registry = dr.async_get(self.hass)
        devices = dr.async_entries_for_config_entry(
            device_registry, self.config_entry.entry_id
        )
        previous_locks = set()
        previous_locks_by_lock_id = {}
        for device in devices:
            for domain, identifier in device.identifiers:
                if domain == DOMAIN:
                    previous_locks.add(identifier)
                    previous_locks_by_lock_id[identifier] = device
                    continue
        current_locks = set(self.data.locks.keys())

        if removed_locks := previous_locks - current_locks:
            LOGGER.debug("Removed locks: %s", ", ".join(removed_locks))
            for lock_id in removed_locks:
                device_registry.async_update_device(
                    device_id=previous_locks_by_lock_id[lock_id].id,
                    remove_config_entry_id=self.config_entry.entry_id,
                )

        if new_lock_ids := current_locks - previous_locks:
            LOGGER.debug("New locks found: %s", ", ".join(new_lock_ids))
            new_locks = {lock_id: self.data.locks[lock_id] for lock_id in new_lock_ids}
            for new_lock_callback in self.new_locks_callbacks:
                new_lock_callback(new_locks)
