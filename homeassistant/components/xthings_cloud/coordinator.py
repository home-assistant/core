"""DataUpdateCoordinator for Xthings Cloud."""

import asyncio
from datetime import timedelta
from functools import partial
import ssl
from typing import Any, override

from ha_xthings_cloud import (
    XthingsCloudApiClient,
    XthingsCloudApiError,
    XthingsCloudAuthError,
    XthingsCloudWebSocket,
)
from ha_xthings_cloud.bulb import (
    SUPPORTED_MODELS,
    NativeBulbClient,
    NativeBulbRoute,
    create_bulb_ssl_context,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_REFRESH_TOKEN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    LOGGER,
    NATIVE_RETRY_INTERVAL,
)

type XthingsCloudConfigEntry = ConfigEntry[XthingsCloudCoordinator]


def _native_status(state: dict[str, int]) -> dict[str, Any]:
    return {
        "on": bool(state["pw"]),
        "brightness": state["br"],
        "color_type": state["ct"],
        "temperature": state["tp"],
        "hue": state["hu"],
        "saturation": state["sa"],
        "lightness": state["li"],
    }


class XthingsCloudCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Xthings Cloud data update coordinator."""

    config_entry: XthingsCloudConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: XthingsCloudApiClient,
        entry: XthingsCloudConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self.native_options = dict(entry.options)
        self.websocket: XthingsCloudWebSocket | None = None
        self.native_bulbs: dict[str, NativeBulbClient] = {}
        self._native_routes: dict[str, NativeBulbRoute] = {}
        self._native_ids: set[str] = set()
        self._native_tls: ssl.SSLContext | None = None
        self._native_retry: CALLBACK_TYPE | None = None
        self._shutting_down = False

    async def _async_ensure_token_valid(self) -> None:
        """Ensure the token is valid, refresh if expired.

        Raises ConfigEntryAuthFailed if refresh fails.
        """
        if not self.client.is_token_expired():
            return
        try:
            token_data = await self.client.async_refresh_token(
                self.config_entry.data[CONF_REFRESH_TOKEN]
            )
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Token expired and refresh failed, re-authentication required"
            ) from err
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={
                **self.config_entry.data,
                CONF_TOKEN: token_data["token"],
                CONF_REFRESH_TOKEN: token_data["refresh_token"],
            },
        )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest device data from cloud."""
        await self._async_ensure_token_valid()
        try:
            devices = await self.client.async_get_devices()
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            ) from err
        except XthingsCloudApiError as err:
            raise UpdateFailed(f"Failed to fetch data: {err}") from err
        if self.config_entry.options.get("native_mqtt", False):
            try:
                await self._async_prepare_native(devices)
            except UpdateFailed as err:
                LOGGER.warning("Native bulb setup failed: %s", err)
            if any(
                (bulb := self.native_bulbs.get(device_id)) is None or bulb.state is None
                for device_id in self._native_ids
            ):
                self._schedule_native_retry()
        result = {}
        for device in devices:
            device_id = device["id"]
            old_status = (self.data or {}).get(device_id, {}).get("status", {})
            device["status"] = {**old_status, **device.get("status", {})}
            if device_id in self._native_ids:
                device = dict(device)
                bulb = self.native_bulbs.get(device_id)
                state = bulb.state if bulb is not None else None
                device["online"] = state is not None
                # Never promote cached HTTP readings to confirmed native state.
                device["status"] = (
                    _native_status(state) if state is not None else dict(old_status)
                )
            result[device_id] = device
        return result

    async def _async_prepare_native(self, devices: list[dict[str, Any]]) -> None:
        self._native_ids = {
            d["id"]
            for d in devices
            if d.get("type") == "light" and d.get("model") in SUPPORTED_MODELS
        }
        for device_id in self.native_bulbs.keys() - self._native_ids:
            self._native_routes.pop(device_id, None)
            await self.native_bulbs.pop(device_id).async_stop()
        # Unavailable bulbs may have been regrouped, which changes their route.
        stale = {
            device_id
            for device_id, bulb in self.native_bulbs.items()
            if bulb.state is None
        }
        pending = (self._native_ids - self.native_bulbs.keys()) | stale
        if not pending or self._shutting_down:
            return
        if self._native_tls is None:
            try:
                self._native_tls = await self.hass.async_add_executor_job(
                    create_bulb_ssl_context,
                )
            except (OSError, ssl.SSLError) as err:
                raise UpdateFailed("Unable to load native MQTT credentials") from err
        try:
            routes = await self.client.async_get_native_bulb_routes()
        except XthingsCloudAuthError as err:
            raise ConfigEntryAuthFailed(
                "Invalid token, re-authentication required"
            ) from err
        except XthingsCloudApiError as err:
            raise UpdateFailed("Unable to discover native bulb routes") from err
        if self._shutting_down:
            # Unload finished while discovery was in flight.
            return
        replaced = []
        starts = []
        for device_id in pending:
            if (route := routes.get(device_id)) is None:
                continue
            if not isinstance(route, NativeBulbRoute):
                route = NativeBulbRoute(route)
            if self._native_routes.get(device_id) == route:
                continue
            if (old := self.native_bulbs.get(device_id)) is not None:
                replaced.append(old.async_stop())
            self._native_routes[device_id] = route
            bulb = self.native_bulbs[device_id] = NativeBulbClient(
                device_id,
                route,
                self._native_tls,
                partial(self._handle_native_state, device_id),
            )
            starts.append(bulb.async_start())
        await asyncio.gather(*replaced)
        await asyncio.gather(*starts)

    def _schedule_native_retry(self) -> None:
        """Retry native setup on its own timer.

        WebSocket updates from other devices reset the account poll timer, so
        waiting for the next poll could postpone recovery indefinitely.
        """
        if self._native_retry is not None or self._shutting_down:
            return
        self._native_retry = async_call_later(
            self.hass, NATIVE_RETRY_INTERVAL, self._async_native_retry
        )

    @callback
    def _async_native_retry(self, _now: Any) -> None:
        self._native_retry = None
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), "xthings_cloud native retry"
        )

    def uses_native_mqtt(self, device_id: str) -> bool:
        """Whether this device requires confirmed native state."""
        return device_id in self._native_ids

    def _handle_native_state(
        self, device_id: str, state: dict[str, int] | None
    ) -> None:
        if not self.data or device_id not in self.data:
            return
        if state is None:
            self._schedule_native_retry()
        device = {**self.data[device_id], "online": state is not None}
        if state is not None:
            device["status"] = _native_status(state)
        # Native health reports must not defer account discovery/token refresh.
        self.data = {**self.data, device_id: device}
        self.async_update_listeners()

    async def async_set_native_state(
        self, device_id: str, changes: dict[str, int]
    ) -> None:
        """Apply native settings and require a fresh device confirmation."""
        bulb = self.native_bulbs.get(device_id)
        if bulb is None:
            raise HomeAssistantError("No native connection for this bulb")
        try:
            await bulb.async_set_state(changes)
        except XthingsCloudApiError as err:
            raise HomeAssistantError(str(err)) from err

    @override
    async def async_shutdown(self) -> None:
        """Stop native clients on entry unload, shutdown, and setup failure."""
        self._shutting_down = True
        if self._native_retry is not None:
            self._native_retry()
            self._native_retry = None
        await super().async_shutdown()
        await asyncio.gather(
            *(bulb.async_stop() for bulb in self.native_bulbs.values())
        )
        self.native_bulbs.clear()
        self._native_routes.clear()

    async def async_start_websocket(self) -> None:
        """Start WebSocket connection."""
        if self.websocket:
            return
        session = async_get_clientsession(self.hass)
        token = self.config_entry.data[CONF_TOKEN]
        self.websocket = XthingsCloudWebSocket(
            session=session,
            token=token,
            on_device_status=self._handle_ws_device_status,
            on_token_expired=self._handle_ws_token_expired,
        )
        await self.websocket.async_start()

    async def async_stop_websocket(self) -> None:
        """Stop WebSocket connection."""
        if self.websocket:
            await self.websocket.async_stop()
            self.websocket = None

    def _handle_ws_device_status(
        self, device_uuid: str, status: dict[str, Any]
    ) -> None:
        """Handle WebSocket device status update."""
        if device_uuid in self._native_ids:
            return
        if not self.data or device_uuid not in self.data:
            LOGGER.debug(
                "WebSocket received status for unknown device: %s", device_uuid
            )
            return
        device_data = self.data[device_uuid]
        device_data.setdefault("status", {}).update(status)
        LOGGER.debug("WebSocket updated device status: %s", device_uuid)
        self.async_set_updated_data(self.data)

    async def _handle_ws_token_expired(self) -> None:
        """Handle WebSocket auth expiry, refresh token."""
        try:
            await self._async_ensure_token_valid()
        except ConfigEntryAuthFailed:
            LOGGER.error("WebSocket token refresh failed")
            return
        new_token = self.config_entry.data[CONF_TOKEN]
        self.client.token = new_token
        if self.websocket:
            self.websocket.token = new_token
        LOGGER.info("WebSocket token refreshed successfully")
