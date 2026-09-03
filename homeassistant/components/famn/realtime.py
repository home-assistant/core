"""Push updates from the Famn realtime gateway."""

from datetime import datetime
from typing import Any

from famn_sdk import ApiClient

# Imported from the submodule, not the package root: `famn_sdk/__init__.py` is
# regenerated from the Swagger spec, while `famn_sdk.realtime` is hand written.
from famn_sdk.realtime import Connected, Event, RealtimeClient, RealtimeError, Rejected

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import EVENT_FAMN_EVENT, LOGGER
from .coordinator import FamnConfigEntry


class FamnRealtime:
    """Feed gateway events into the data coordinators.

    Polling stays on as a fallback; this only makes updates immediate.
    """

    def __init__(
        self, hass: HomeAssistant, entry: FamnConfigEntry, client: ApiClient
    ) -> None:
        """Initialize the realtime listener."""
        self.hass = hass
        self.entry = entry
        self.auth = entry.runtime_data.chores.auth
        self._client = RealtimeClient(
            client,
            self._async_token,
            session=async_get_clientsession(hass),
        )
        # Which coordinator each gateway topic feeds. Topics on the space
        # channel that have no entities here (chats, ...) are simply not in
        # the map.
        self._topic_coordinators: dict[str, DataUpdateCoordinator[Any]] = {
            "TaskList": entry.runtime_data.chores,
            "TaskItem": entry.runtime_data.chores,
            "Calendar": entry.runtime_data.calendars,
            "SpaceScore": entry.runtime_data.scores,
            "List": entry.runtime_data.shopping,
            "ListItem": entry.runtime_data.shopping,
            "MealSlot": entry.runtime_data.meals,
        }

    async def _async_token(self) -> tuple[str, datetime]:
        """Return a valid access token and when it should be renewed."""
        return await self.auth.async_get_access_token(), self.auth.reauth_at

    async def async_run(self) -> None:
        """Consume gateway messages until the entry is unloaded.

        Runs as a config entry background task, so cancellation is the
        shutdown signal.
        """
        try:
            async for message in self._client.listen():
                match message:
                    case Connected():
                        # Anything that changed while the socket was down was
                        # missed, so reconcile every coordinator once.
                        for coordinator in dict.fromkeys(
                            self._topic_coordinators.values()
                        ):
                            await coordinator.async_request_refresh()
                    case Rejected():
                        # The gateway found the token invalid even though its
                        # expiry looked fine locally (a revoked device, or a
                        # clock skew). Rotating on the next attempt either
                        # fixes the mismatch or surfaces the revocation as
                        # ConfigEntryAuthFailed instead of retrying forever.
                        self.auth.invalidate()
                    case Event():
                        await self._async_handle_event(message)
        except ConfigEntryAuthFailed:
            # The device registration is gone; reconnecting cannot fix that,
            # only pairing again can.
            self.entry.async_start_reauth(self.hass)
        except RealtimeError as err:
            LOGGER.debug("Famn realtime listener stopped: %s", err)

    async def _async_handle_event(self, event: Event) -> None:
        """Put the event on the bus and refresh whatever it touches."""
        # Every event goes on the bus — automations react to any family
        # activity, entities or not.
        self.hass.bus.async_fire(
            EVENT_FAMN_EVENT,
            {
                "topic": event.topic,
                "action": event.action,
                "space_id": event.space_id,
                "event_id": event.event_id,
                "payload": event.payload,
            },
        )
        if coordinator := self._topic_coordinators.get(event.topic or ""):
            await coordinator.async_request_refresh()
