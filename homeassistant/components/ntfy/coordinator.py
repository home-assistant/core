"""DataUpdateCoordinator for ntfy integration."""

import asyncio
from asyncio import Task
from datetime import timedelta
import logging

from aiontfy import Notification, Ntfy
from aiontfy.exceptions import NtfyConnectionError, NtfyTimeoutError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, NTFY_EVENT

type NtfyConfigEntry = ConfigEntry[NtfyDataUpdateCoordinator]

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


class NtfyDataUpdateCoordinator(DataUpdateCoordinator[Notification | None]):
    """Ntfy DataUpdateCoordinator."""

    config_entry: NtfyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: NtfyConfigEntry,
        ntfy: Ntfy,
    ) -> None:
        """Initialize the Bring data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.ntfy = ntfy
        self.topics: set[str] | None = None
        self._ws: Task | None = None

    async def _async_update_data(self) -> None:
        """Connect websocket."""
        topics = set(self.async_contexts())

        try:
            if self._ws and (exc := self._ws.exception()):
                raise exc
        except asyncio.InvalidStateError:
            pass
        except asyncio.CancelledError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_closed",
            ) from e
        except NtfyConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
            ) from e
        except NtfyTimeoutError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_error",
            ) from e
        finally:
            if (self._ws is None or self._ws.done()) and topics:
                self._ws = self.config_entry.async_create_background_task(
                    hass=self.hass,
                    target=self.ntfy.subscribe(
                        topics=list(topics),
                        callback=lambda data: async_dispatcher_send(
                            self.hass,
                            f"{NTFY_EVENT}_{self.config_entry.entry_id}",
                            data,
                        ),
                    ),
                    name="ntfy_websocket",
                )

                self.topics = topics
