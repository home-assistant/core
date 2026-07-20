"""Data update coordinator for the Elke27 integration."""

import asyncio
from collections.abc import Callable
import logging
from typing import Any, override

from elke27_lib import ArmMode, ClientConfig, LinkKeys, PanelSnapshot
from elke27_lib.client import Elke27Client
from elke27_lib.errors import (
    Elke27ConnectionError,
    Elke27DisconnectedError,
    Elke27LinkRequiredError,
    Elke27PinRequiredError,
    Elke27TimeoutError,
    InvalidCredentials,
)
from elke27_lib.events import (
    ConnectionStateChanged,
    CsmSnapshotUpdated,
    DomainCsmChanged,
    TableCsmChanged,
    ZoneStatusUpdated,
)

from homeassistant.const import CONF_CLIENT_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LINK_KEYS_JSON, DOMAIN, READY_TIMEOUT
from .identity import build_client_identity
from .models import Elke27ConfigEntry

_LOGGER = logging.getLogger(__name__)
_CONNECT_FAILED = "Unable to connect to the panel; check host and port"
_REFRESH_FAILED = "Unable to refresh panel data"
_DEBOUNCE_SECONDS = 0.3


class Elke27DataUpdateCoordinator(DataUpdateCoordinator[PanelSnapshot]):
    """Coordinate Elke27 client lifecycle and snapshot updates."""

    config_entry: Elke27ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: Elke27ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self._host: str = entry.data[CONF_HOST]
        self._port: int = entry.data[CONF_PORT]
        self._link_keys_json: str = entry.data[CONF_LINK_KEYS_JSON]
        self._client_id: str = entry.data[CONF_CLIENT_ID]
        self._client: Elke27Client | None = None
        self._connection_unsubscribe: Callable[[], None] | None = None
        self._event_unsubscribe: Callable[[], None] | None = None
        self._pending_domains: set[str] = set()
        self._refresh_lock = asyncio.Lock()
        self._debounce_task: asyncio.Task[None] | None = None

    @property
    def is_ready(self) -> bool:
        """Return whether the client is connected and ready."""
        client = self._client
        return client is not None and client.is_ready

    @property
    def panel_name(self) -> str | None:
        """Return the panel name from the current snapshot."""
        return self.data.panel.panel_name if self.data else None

    @override
    async def _async_setup(self) -> None:
        """Connect to the panel and subscribe to its events."""
        try:
            link_keys = LinkKeys.from_json(self._link_keys_json)
        except (AttributeError, KeyError, TypeError, ValueError) as err:
            msg = "Linking credentials are invalid"
            raise ConfigEntryAuthFailed(msg) from err

        client = Elke27Client(ClientConfig())
        client.set_client_identity(build_client_identity(self._client_id))

        try:
            await client.async_connect(
                host=self._host, port=self._port, link_keys=link_keys
            )
            ready = await client.wait_ready(timeout_s=READY_TIMEOUT)
        except (Elke27LinkRequiredError, InvalidCredentials) as err:
            await _async_disconnect_client(client)
            msg = "Panel requires linking; configure the integration again"
            raise ConfigEntryAuthFailed(msg) from err
        except (
            Elke27ConnectionError,
            Elke27TimeoutError,
            Elke27DisconnectedError,
        ) as err:
            await _async_disconnect_client(client)
            raise UpdateFailed(_CONNECT_FAILED) from err

        if not ready:
            await _async_disconnect_client(client)
            raise UpdateFailed(_CONNECT_FAILED)

        self._client = client
        self._connection_unsubscribe = client.subscribe(self._handle_connection_event)
        self._event_unsubscribe = client.subscribe_typed(self._handle_event)

    async def async_disconnect(self) -> None:
        """Disconnect the panel client and unregister event handlers."""
        await self._cancel_debounce_task()
        if self._event_unsubscribe is not None:
            self._event_unsubscribe()
            self._event_unsubscribe = None
        if self._connection_unsubscribe is not None:
            self._connection_unsubscribe()
            self._connection_unsubscribe = None
        client = self._client
        self._client = None
        if client is not None:
            await client.async_disconnect()

    @override
    async def _async_update_data(self) -> PanelSnapshot:
        """Perform a full CSM refresh and return the latest snapshot."""
        async with self._refresh_lock:
            client = self._require_client()
            try:
                await client.async_refresh_csm()
            except (
                Elke27ConnectionError,
                Elke27TimeoutError,
                Elke27DisconnectedError,
            ) as err:
                raise UpdateFailed(_REFRESH_FAILED) from err
            snapshot = client.get_snapshot()
            if snapshot is None:
                raise UpdateFailed(_REFRESH_FAILED)
            return snapshot

    async def async_set_zone_bypass(
        self, zone_id: int, *, bypassed: bool, pin: str | None = None
    ) -> bool:
        """Request a zone bypass change."""
        if pin is None:
            msg = "PIN required to bypass zones."
            raise Elke27PinRequiredError(msg)
        try:
            result = await self._require_client().async_set_zone_bypass(
                zone_id, bypassed=bypassed, pin=pin
            )
        except Elke27PinRequiredError:
            raise
        except (
            Elke27ConnectionError,
            Elke27TimeoutError,
            Elke27DisconnectedError,
        ) as err:
            raise UpdateFailed(_REFRESH_FAILED) from err
        return _command_succeeded("Zone bypass", result)

    async def async_arm_area(
        self,
        area_id: int,
        mode: ArmMode,
        pin: str | None,
        *,
        auto_stay_cancel: bool = False,
        exit_delay_cancel: bool = False,
    ) -> bool:
        """Request an area arming change."""
        if pin is None:
            msg = "PIN required to arm areas."
            raise Elke27PinRequiredError(msg)
        try:
            result = await self._require_client().async_arm_area(
                area_id,
                mode=mode,
                pin=pin,
                auto_stay_cancel=auto_stay_cancel,
                exit_delay_cancel=exit_delay_cancel,
            )
        except Elke27PinRequiredError:
            raise
        except (
            Elke27ConnectionError,
            Elke27TimeoutError,
            Elke27DisconnectedError,
        ) as err:
            raise UpdateFailed(_REFRESH_FAILED) from err
        return _command_succeeded("Area arming", result)

    async def async_disarm_area(
        self,
        area_id: int,
        pin: str | None,
        *,
        auto_stay_cancel: bool = False,
        exit_delay_cancel: bool = False,
    ) -> bool:
        """Request an area disarming change."""
        if pin is None:
            msg = "PIN required to disarm areas."
            raise Elke27PinRequiredError(msg)
        try:
            result = await self._require_client().async_disarm_area(
                area_id,
                pin=pin,
                auto_stay_cancel=auto_stay_cancel,
                exit_delay_cancel=exit_delay_cancel,
            )
        except Elke27PinRequiredError:
            raise
        except (
            Elke27ConnectionError,
            Elke27TimeoutError,
            Elke27DisconnectedError,
        ) as err:
            raise UpdateFailed(_REFRESH_FAILED) from err
        return _command_succeeded("Area disarm", result)

    def _require_client(self) -> Elke27Client:
        """Return the active client or raise a consistent HA error."""
        if self._client is None:
            msg = "Client is not connected."
            raise HomeAssistantError(msg)
        return self._client

    def _handle_connection_event(self, event: ConnectionStateChanged) -> None:
        """Handle connection lifecycle events from the client."""
        self.hass.loop.call_soon_threadsafe(self._process_event, event)

    def _handle_event(self, event: Any) -> None:
        """Handle typed client events from the Home Assistant event loop."""
        self.hass.loop.call_soon_threadsafe(self._process_event, event)

    @callback
    def _process_event(self, event: Any) -> None:
        """Process an event from the client."""
        if isinstance(event, ZoneStatusUpdated):
            _LOGGER.debug(
                "Zone status event received: zone_id=%s changed_fields=%s",
                event.zone_id,
                event.changed_fields,
            )
        if isinstance(event, ConnectionStateChanged):
            if event.connected:
                self.config_entry.async_create_task(self.hass, self.async_refresh())
            else:
                self._set_snapshot(_client_snapshot(self._client))
            return
        if isinstance(event, CsmSnapshotUpdated):
            self._set_snapshot(_client_snapshot(self._client))
            return
        if isinstance(event, (DomainCsmChanged, TableCsmChanged)):
            if domain := event.csm_domain:
                self._queue_domain_refresh(str(domain))
            return
        self._set_snapshot(_client_snapshot(self._client))

    def _queue_domain_refresh(self, domain: str) -> None:
        """Queue a debounced config refresh for a CSM domain."""
        self._pending_domains.add(domain)
        if self._debounce_task is None or self._debounce_task.done():
            self._debounce_task = self.config_entry.async_create_task(
                self.hass, self._async_debounced_refresh()
            )

    async def _async_debounced_refresh(self) -> None:
        """Refresh pending domains after a short debounce delay."""
        await asyncio.sleep(_DEBOUNCE_SECONDS)
        async with self._refresh_lock:
            if (client := self._client) is None:
                return
            while self._pending_domains:
                domains = tuple(self._pending_domains)
                self._pending_domains.clear()
                for domain in domains:
                    try:
                        await client.async_refresh_domain_config(domain)
                    except (
                        Elke27ConnectionError,
                        Elke27TimeoutError,
                        Elke27DisconnectedError,
                    ):
                        # Reconnecting triggers a full refresh; drop this one.
                        return
        self._set_snapshot(client.get_snapshot())

    async def _cancel_debounce_task(self) -> None:
        """Cancel a pending debounced refresh."""
        if (task := self._debounce_task) is None:
            return
        self._debounce_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return

    def _set_snapshot(self, snapshot: PanelSnapshot | None) -> None:
        """Update coordinator data from a panel snapshot."""
        self.async_set_updated_data(snapshot or PanelSnapshot.empty())


async def _async_disconnect_client(client: Elke27Client) -> None:
    """Disconnect a client after setup failure."""
    try:
        await client.async_disconnect()
    except Elke27ConnectionError, Elke27TimeoutError, Elke27DisconnectedError:
        return


def _client_snapshot(client: Elke27Client | None) -> PanelSnapshot | None:
    """Return a client snapshot if a client is connected."""
    return client.get_snapshot() if client is not None else None


def _raise_command_error(action: str, error: BaseException) -> None:
    """Raise a Home Assistant error for a failed client command."""
    detail = str(error)
    message = f"{action} failed: {detail}" if detail else f"{action} failed."
    raise HomeAssistantError(message) from error


def _command_succeeded(action: str, result: Any) -> bool:
    """Return whether a client command result was accepted."""
    if result is None:
        return True
    if isinstance(result, bool):
        return result
    if result.ok:
        return True
    error = result.error
    if isinstance(error, BaseException):
        _raise_command_error(action, error)
    if error:
        msg = f"{action} failed: {error}"
        raise HomeAssistantError(msg)
    return False
