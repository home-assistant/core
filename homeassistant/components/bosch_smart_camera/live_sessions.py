"""Local live-stream sessions of the Bosch Smart Camera integration."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import logging
import ssl
from typing import TYPE_CHECKING, Any

from bosch_shc_camera_client.cameras import (
    BoschCameraAuthError,
    BoschCameraConnectionError,
    BoschCameraInvalidResponseError,
)
from bosch_shc_camera_client.live import LiveConnection, open_local_live_connection
from bosch_shc_camera_client.tls_proxy import (
    pre_warm_rtsp,
    start_tls_proxy,
    stop_all_proxies,
    stop_tls_proxy,
)

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.util.ssl import create_no_verify_ssl_context

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)

# Renew before the session management of the camera ends the session.
RENEW_MARGIN = 300


@dataclass
class _Session:
    """A live session of one camera and its TLS proxy."""

    url: str
    is_streaming: Callable[[], bool]
    on_changed: Callable[[str | None], None]
    cancel_renewal: CALLBACK_TYPE


class LiveSessions:
    """Open, renew and close the local live sessions of the cameras."""

    def __init__(self, coordinator: BoschCameraCoordinator) -> None:
        """Initialize the sessions."""
        self._coordinator = coordinator
        self._ssl_context: ssl.SSLContext | None = None
        self._sessions: dict[str, _Session] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._ports: dict[str, int] = {}
        self._servers: dict[str, asyncio.base_events.Server] = {}
        self._opening: dict[str, asyncio.Task[_Session]] = {}
        self._renewals: dict[str, asyncio.Task[None]] = {}
        self._proxies: dict[str, object] = {}

    @property
    def camera_ids(self) -> set[str]:
        """Return the cameras with a session or one being opened."""
        return self._sessions.keys() | self._opening.keys()

    async def async_get_url(
        self,
        camera_id: str,
        is_streaming: Callable[[], bool],
        on_changed: Callable[[str | None], None],
    ) -> str:
        """Return the stream address of the camera, opening a session if needed."""
        if session := self._sessions.get(camera_id):
            return session.url
        # Home Assistant gives up on a slow source after 10 seconds. The open
        # runs on in the background so the next request picks up its result.
        if (task := self._opening.get(camera_id)) is None or task.done():
            task = self._opening[camera_id] = (
                self._coordinator.config_entry.async_create_background_task(
                    self._coordinator.hass,
                    self._async_open_once(camera_id, is_streaming, on_changed),
                    f"{DOMAIN} live session {camera_id}",
                )
            )
            task.add_done_callback(partial(self._opened, camera_id))
        return (await asyncio.shield(task)).url

    def _opened(self, camera_id: str, task: asyncio.Task[_Session]) -> None:
        if self._opening.get(camera_id) is task:
            del self._opening[camera_id]
        if not task.cancelled():
            task.exception()

    async def _async_open_once(
        self,
        camera_id: str,
        is_streaming: Callable[[], bool],
        on_changed: Callable[[str | None], None],
    ) -> _Session:
        async with self._locks[camera_id]:
            # A renewal may have installed a session while this waited.
            if session := self._sessions.get(camera_id):
                return session
            return await self._async_open(camera_id, is_streaming, on_changed)

    async def async_close(self, camera_id: str) -> None:
        """Close the session of a camera."""
        await self._async_cancel_tasks([camera_id])
        async with self._locks[camera_id]:
            await self._async_close(camera_id)
        self._locks.pop(camera_id, None)

    async def async_close_all(self) -> None:
        """Close all sessions."""
        await self._async_cancel_tasks([*self._opening, *self._renewals])
        for session in self._sessions.values():
            session.cancel_renewal()
        self._sessions.clear()
        await stop_all_proxies(self._ports, self._servers)

    async def _async_cancel_tasks(self, camera_ids: list[str]) -> None:
        """Stop opens and renewals in flight and wait until they unwound."""
        tasks = [
            task
            for camera_id in camera_ids
            for task in (
                self._opening.get(camera_id),
                self._renewals.get(camera_id),
            )
            if task is not None
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        # The done callback runs a loop iteration later, so drop the entries here.
        for camera_id in camera_ids:
            self._opening.pop(camera_id, None)

    async def _async_close(self, camera_id: str) -> None:
        proxy = self._proxies.pop(camera_id, None)
        if session := self._sessions.pop(camera_id, None):
            session.cancel_renewal()
        if proxy is not None:
            await stop_tls_proxy(camera_id, self._ports, self._servers)

    async def _async_open(
        self,
        camera_id: str,
        is_streaming: Callable[[], bool],
        on_changed: Callable[[str | None], None],
    ) -> _Session:
        """Open a session; every call rotates the camera's credentials."""
        coordinator = self._coordinator
        token = await coordinator.async_get_access_token()
        try:
            connection = await open_local_live_connection(
                async_get_clientsession(coordinator.hass), token, camera_id
            )
        except BoschCameraAuthError as err:
            coordinator.config_entry.async_start_reauth_if_available(coordinator.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="auth_failed"
            ) from err
        except (BoschCameraConnectionError, BoschCameraInvalidResponseError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="stream_failed"
            ) from err
        url = await self._async_start_proxy(camera_id, connection)
        session = _Session(url, is_streaming, on_changed, lambda: None)
        self._schedule(
            camera_id,
            session,
            max(connection.max_session_seconds - RENEW_MARGIN, 1),
            self._async_renew,
        )
        self._sessions[camera_id] = session
        return session

    async def _async_start_proxy(
        self, camera_id: str, connection: LiveConnection
    ) -> str:
        """Start the TLS proxy of the session and wake the camera's encoder."""
        if self._ssl_context is None:
            # Building the context reads the CA store, which blocks.
            self._ssl_context = await self._coordinator.hass.async_add_executor_job(
                create_no_verify_ssl_context
            )
        proxy = self._proxies[camera_id] = object()
        try:
            port = await start_tls_proxy(
                self._ssl_context,
                camera_id,
                connection.host,
                connection.port,
                self._ports,
                self._servers,
                on_proxy_died=partial(self._proxy_died, camera_id, proxy),
            )
        except OSError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="stream_failed"
            ) from err
        if not await pre_warm_rtsp(
            port,
            connection.username,
            connection.password,
            connection.host,
            max_session_duration=connection.max_session_seconds,
        ):
            await stop_tls_proxy(camera_id, self._ports, self._servers)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="stream_failed"
            )
        return connection.stream_url(port)

    @callback
    def _proxy_died(self, camera_id: str, proxy: object) -> None:
        """Drop the session so the next request opens a new one."""
        # The library reports a dead proxy late, when a newer one may be running.
        if self._proxies.get(camera_id) is not proxy:
            return
        if session := self._sessions.pop(camera_id, None):
            session.cancel_renewal()
            session.on_changed(None)

    def _schedule(
        self,
        camera_id: str,
        session: _Session,
        delay: float,
        action: Callable[[str, _Session], Coroutine[Any, Any, None]],
    ) -> None:
        """Run an action on the session later, owned by the config entry."""

        @callback
        def run(_now: datetime) -> None:
            task = self._renewals[camera_id] = (
                self._coordinator.config_entry.async_create_background_task(
                    self._coordinator.hass,
                    action(camera_id, session),
                    f"{DOMAIN} live session {camera_id}",
                )
            )
            task.add_done_callback(partial(self._renewed, camera_id))

        session.cancel_renewal = async_call_later(self._coordinator.hass, delay, run)

    def _renewed(self, camera_id: str, task: asyncio.Task[None]) -> None:
        if self._renewals.get(camera_id) is task:
            del self._renewals[camera_id]

    async def _async_renew(self, camera_id: str, session: _Session) -> None:
        """Replace the session shortly before it ends, while a viewer uses it."""
        async with self._locks[camera_id]:
            if self._sessions.get(camera_id) is not session:
                return
            if not session.is_streaming():
                # Consumers that are invisible here (go2rtc) keep this address
                # until the session management of the camera ends it.
                self._schedule(camera_id, session, RENEW_MARGIN, self._async_expire)
                return
            await self._async_replace(camera_id, session)

    async def _async_replace(self, camera_id: str, session: _Session) -> None:
        """Open the next session, or end the camera's stream if that fails."""
        try:
            renewed = await self._async_open(
                camera_id, session.is_streaming, session.on_changed
            )
        except HomeAssistantError, TimeoutError:
            _LOGGER.warning("Could not renew the live session of a camera")
            await self._async_close(camera_id)
            session.on_changed(None)
            return
        session.on_changed(renewed.url)

    async def _async_expire(self, camera_id: str, session: _Session) -> None:
        """Drop an unused session once the camera has ended it."""
        async with self._locks[camera_id]:
            if self._sessions.get(camera_id) is not session:
                return
            if session.is_streaming():
                # A viewer started after the last check.
                await self._async_replace(camera_id, session)
                return
            await self._async_close(camera_id)
            session.on_changed(None)
