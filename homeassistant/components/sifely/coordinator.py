"""DataUpdateCoordinator for the Sifely smart lock integration."""

from datetime import timedelta
import logging
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pysifely import LOCK_STATE_UNKNOWN, SifelyApiClient, SifelyApiError, SifelyAuthError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SifelyConfigEntry = ConfigEntry[SifelyDataUpdateCoordinator]


class SifelyDataUpdateCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Coordinator that polls every lock's state and detail in one place."""

    config_entry: SifelyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SifelyConfigEntry,
        client: SifelyApiClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.locks: list[dict[str, Any]] = []

    @override
    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch the lock list, then each lock's state and detail.

        Returns a mapping of lock_id to {"info", "detail", "state"}.
        """
        try:
            locks = await self.client.get_locks()
        except SifelyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SifelyApiError as err:
            raise UpdateFailed(str(err)) from err

        self.locks = locks
        data: dict[int, dict[str, Any]] = {}

        for lock in locks:
            lock_id = lock.get("lockId")
            if lock_id is None:
                _LOGGER.debug("Skipping lock without lockId: %s", lock)
                continue

            detail: dict[str, Any] = {}
            state = LOCK_STATE_UNKNOWN
            try:
                detail = await self.client.get_lock_detail(lock_id)
            except SifelyApiError as err:
                _LOGGER.debug("Failed to fetch detail for lock %s: %s", lock_id, err)
            try:
                state = await self.client.get_lock_state(lock_id)
            except SifelyApiError as err:
                _LOGGER.debug("Failed to fetch state for lock %s: %s", lock_id, err)

            data[lock_id] = {"info": lock, "detail": detail, "state": state}

        return data
