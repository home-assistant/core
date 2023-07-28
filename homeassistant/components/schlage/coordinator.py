"""DataUpdateCoordinator for the Schlage integration."""
from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from pyschlage import Lock, Schlage
from pyschlage.code import AccessCode
from pyschlage.exceptions import Error as SchlageError
from pyschlage.log import LockLog
from pyschlage.user import User

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


@dataclass
class LockData:
    """Container for cached lock data from the Schlage API."""

    lock: Lock
    logs: list[LockLog]
    access_codes: dict[str, AccessCode]


@dataclass
class SchlageData:
    """Container for cached data from the Schlage API."""

    locks: dict[str, LockData]
    users: dict[str, User]


class SchlageDataUpdateCoordinator(DataUpdateCoordinator[SchlageData]):
    """The Schlage data update coordinator."""

    def __init__(self, hass: HomeAssistant, username: str, api: Schlage) -> None:
        """Initialize the class."""
        super().__init__(
            hass, LOGGER, name=f"{DOMAIN} ({username})", update_interval=UPDATE_INTERVAL
        )
        self.api = api

    async def _async_update_data(self) -> SchlageData:
        """Fetch the latest data from the Schlage API."""
        try:
            locks: list[Lock] = await self.hass.async_add_executor_job(self.api.locks)
        except SchlageError as ex:
            raise UpdateFailed("Failed to refresh Schlage data") from ex
        lock_data = await asyncio.gather(
            *(
                self.hass.async_add_executor_job(self._get_lock_data, lock)
                for lock in locks
            )
        )
        users: Iterable[User] = []
        if self.data:
            # Default to the previous data, in case a refresh fails.
            # It's not critical if we don't have the freshest data.
            users = self.data.users.values()
        try:
            users = await self.hass.async_add_executor_job(self.api.users)
        except SchlageError as ex:
            LOGGER.warning("Failed to read Schlage users: %s", ex)

        return SchlageData(
            locks={ld.lock.device_id: ld for ld in lock_data},
            users={u.user_id: u for u in users},
        )

    def _get_lock_data(self, lock: Lock) -> LockData:
        access_codes: dict[str, AccessCode] = {}
        logs: list[LockLog] = []
        previous_lock_data = None
        if self.data and (previous_lock_data := self.data.locks.get(lock.device_id)):
            # Default to the previous data, in case a refresh fails.
            # It's not critical if we don't have the freshest data.
            access_codes = previous_lock_data.access_codes
            logs = previous_lock_data.logs
        try:
            access_codes = {ac.access_code_id: ac for ac in lock.access_codes()}
        except SchlageError as ex:
            LOGGER.warning(
                'Failed to read access codes for lock "%s": %s', lock.name, ex
            )
        try:
            logs = lock.logs()
        except SchlageError as ex:
            LOGGER.warning('Failed to read logs for lock "%s": %s', lock.name, ex)
        return LockData(lock=lock, access_codes=access_codes, logs=logs)
