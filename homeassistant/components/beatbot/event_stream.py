"""Beatbot cloud event handling."""

import asyncio
from contextlib import suppress
import logging

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotClient,
    BeatbotConnectionError,
    BeatbotEvent,
    BeatbotEventClient as BeatbotCloudEventClient,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import BeatbotCoordinator

_LOGGER = logging.getLogger(__name__)


class BeatbotEventClient:
    """Connect library events to Home Assistant state."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
        api: BeatbotClient,
        coordinator: BeatbotCoordinator,
    ) -> None:
        """Initialize the Beatbot event client."""
        self._hass = hass
        self._entry = entry
        self._oauth_session = oauth_session
        self._coordinator = coordinator
        self._task: asyncio.Task[None] | None = None
        self._client = BeatbotCloudEventClient(
            async_get_clientsession(hass),
            api.event_stream_url,
            api.async_get_access_token,
            self._handle_event,
            reconnect_callback=coordinator.async_request_refresh,
            token_refresh_callback=self._async_refresh_token,
        )
        self._reload_scheduled = False

    def async_start(self) -> None:
        """Start the connection supervisor without blocking setup."""
        if self._task is None or self._task.done():
            self._task = self._entry.async_create_background_task(
                self._hass,
                self._run(),
                f"beatbot_event_stream_{self._entry.entry_id}",
            )

    async def async_stop(self) -> None:
        """Stop and close the stream. Safe to call repeatedly."""
        await self._client.async_close()
        task, self._task = self._task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _run(self) -> None:
        """Run the library event client and start reauthentication if needed."""
        try:
            await self._client.async_run()
        except BeatbotAuthenticationError:
            _LOGGER.warning(
                "Beatbot event stream authorization failed; starting reauthentication"
            )
            self._entry.async_start_reauth(self._hass)

    async def _async_refresh_token(self, rejected_access_token: str) -> str:
        """Refresh a rejected token through the session's shared rotation lock."""
        current_token = self._oauth_session.token
        if current_token.get("access_token") == rejected_access_token:
            self._hass.config_entries.async_update_entry(
                self._entry,
                data={
                    **self._entry.data,
                    "token": {**current_token, "expires_at": 0},
                },
            )
            try:
                await self._oauth_session.async_ensure_token_valid()
            except (OAuth2TokenRequestReauthError, ConfigEntryAuthFailed) as err:
                raise BeatbotAuthenticationError from err
            except Exception as err:
                raise BeatbotConnectionError("OAuth token refresh failed") from err

        access_token = self._oauth_session.token.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise BeatbotAuthenticationError
        return access_token

    def _handle_event(self, event: BeatbotEvent) -> None:
        """Apply one validated event to Home Assistant state."""
        event_type = event.event_type
        device_id = event.device_id
        _LOGGER.debug(
            "Received Beatbot event eventId=%s deviceId=%s type=%s",
            event.event_id,
            device_id,
            event_type,
        )

        if event_type in ("properties_changed", "status"):
            self._coordinator.async_apply_device_event(event)
        elif event_type == "device_added":
            self._schedule_entry_reload()
        elif event_type == "device_removed":
            self._remove_device_from_registries(device_id)
            self._schedule_entry_reload()
        else:
            _LOGGER.debug("Ignoring unknown Beatbot event type %s", event_type)

    def _schedule_entry_reload(self) -> None:
        """Reload all platforms after the account's device set changes."""
        if self._reload_scheduled:
            return
        self._reload_scheduled = True
        self._hass.config_entries.async_schedule_reload(self._entry.entry_id)

    def _remove_device_from_registries(self, device_id: str) -> None:
        """Remove entities and the device registry entry after account removal."""
        device_registry = dr.async_get(self._hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), self._entry.entry_id
        )
        if device is None:
            return

        entity_registry = er.async_get(self._hass)
        for entity in er.async_entries_for_device(
            entity_registry, device.id, include_disabled_entities=True
        ):
            if entity.config_entry_id == self._entry.entry_id:
                entity_registry.async_remove(entity.entity_id)
        device_registry.async_update_device(
            device.id, remove_config_entry_id=self._entry.entry_id
        )
