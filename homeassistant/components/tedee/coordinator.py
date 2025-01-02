"""Coordinator for Tedee locks."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
import logging
import time
from typing import Any

from aiotedee import (
    TedeeClient,
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
    TedeeLock,
    TedeeWebhookException,
)
from aiotedee.bridge import TedeeBridge

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN

SCAN_INTERVAL = timedelta(seconds=30)
GET_LOCKS_INTERVAL_SECONDS = 3600

_LOGGER = logging.getLogger(__name__)

type TedeeConfigEntry = ConfigEntry[TedeeApiCoordinator]


class TedeeApiCoordinator(DataUpdateCoordinator[dict[int, TedeeLock]]):
    """Class to handle fetching data from the tedee API centrally."""

    config_entry: TedeeConfigEntry
    bridge: TedeeBridge

    def __init__(self, hass: HomeAssistant, entry: TedeeConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.tedee_client = TedeeClient(
            local_token=self.config_entry.data[CONF_LOCAL_ACCESS_TOKEN],
            local_ip=self.config_entry.data[CONF_HOST],
            session=async_get_clientsession(hass),
        )

        self._next_get_locks = time.time()
        self._locks_last_update: set[int] = set()
        self.new_lock_callbacks: list[Callable[[int], None]] = []
        self.tedee_webhook_id: int | None = None

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        async def _async_get_bridge() -> None:
            self.bridge = await self.tedee_client.get_local_bridge()

        _LOGGER.debug("Update coordinator: Getting bridge from API")
        await self._async_update(_async_get_bridge)

    async def _async_update_data(self) -> dict[int, TedeeLock]:
        """Fetch data from API endpoint."""

        _LOGGER.debug("Update coordinator: Getting locks from API")
        # once every hours get all lock details, otherwise use the sync endpoint
        if self._next_get_locks <= time.time():
            _LOGGER.debug("Updating through /my/lock endpoint")
            await self._async_update(self.tedee_client.get_locks)
            self._next_get_locks = time.time() + GET_LOCKS_INTERVAL_SECONDS
        else:
            _LOGGER.debug("Updating through /sync endpoint")
            await self._async_update(self.tedee_client.sync)

        _LOGGER.debug(
            "available_locks: %s",
            ", ".join(map(str, self.tedee_client.locks_dict.keys())),
        )

        self._async_add_remove_locks()
        return self.tedee_client.locks_dict

    async def _async_update(self, update_fn: Callable[[], Awaitable[None]]) -> None:
        """Update locks based on update function."""
        try:
            await update_fn()
        except TedeeLocalAuthException as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="authentification_failed",
            ) from ex

        except TedeeDataUpdateException as ex:
            _LOGGER.debug("Error while updating data: %s", str(ex))
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="update_failed"
            ) from ex
        except (TedeeClientException, TimeoutError) as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from ex

    def webhook_received(self, message: dict[str, Any]) -> None:
        """Handle webhook message."""
        self.tedee_client.parse_webhook_message(message)
        self.async_set_updated_data(self.tedee_client.locks_dict)

    async def async_register_webhook(self, webhook_url: str) -> None:
        """Register the webhook at the Tedee bridge."""
        self.tedee_webhook_id = await self.tedee_client.register_webhook(webhook_url)

    async def async_unregister_webhook(self) -> None:
        """Unregister the webhook at the Tedee bridge."""
        if self.tedee_webhook_id is not None:
            try:
                await self.tedee_client.delete_webhook(self.tedee_webhook_id)
            except TedeeWebhookException:
                _LOGGER.exception("Failed to unregister Tedee webhook from bridge")
            else:
                _LOGGER.debug("Unregistered Tedee webhook")

    def _async_add_remove_locks(self) -> None:
        """Add new locks, remove non-existing locks."""
        if not self._locks_last_update:
            self._locks_last_update = set(self.tedee_client.locks_dict)

        if (
            current_locks := set(self.tedee_client.locks_dict)
        ) == self._locks_last_update:
            return

        # remove old locks
        if removed_locks := self._locks_last_update - current_locks:
            _LOGGER.debug("Removed locks: %s", ", ".join(map(str, removed_locks)))
            device_registry = dr.async_get(self.hass)
            for lock_id in removed_locks:
                if device := device_registry.async_get_device(
                    identifiers={(DOMAIN, str(lock_id))}
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )

        # add new locks
        if new_locks := current_locks - self._locks_last_update:
            _LOGGER.debug("New locks found: %s", ", ".join(map(str, new_locks)))
            for lock_id in new_locks:
                for callback in self.new_lock_callbacks:
                    callback(lock_id)

        self._locks_last_update = current_locks
