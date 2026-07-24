"""Coordinator for the GARDENA smart local gateway WebSocket connection."""

import asyncio
import base64
import contextlib
from dataclasses import dataclass
import logging
from typing import override

import aiohttp
from gardena_smart_local_api.devices import (
    Device,
    DeviceMap,
    build_discovery_obj,
    build_inclusion_obj,
    create_devices_from_messages,
)
from gardena_smart_local_api.messages import (
    EgressMessageList,
    Event,
    IngressMessageList,
    Reply,
)
from gardena_smart_local_api.sgtin96 import SGTIN96Info
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.ssl import get_default_no_verify_context

INCLUDE_REPLY_TIMEOUT = 10
EXCLUDE_REPLY_TIMEOUT = 10
INCLUDABLE_DEVICE_HEARTBEAT_TIMEOUT = 25
INCLUSION_TIMEOUT = 30


@dataclass
class IncludableDeviceInfo:
    """Information about a device discovered in inclusion mode."""

    instance_id: str
    service: str
    device_id: str
    device_name: str


_LOGGER = logging.getLogger(__name__)


class GardenaSmartLocalCoordinator(DataUpdateCoordinator[DeviceMap]):
    """Coordinator that maintains the WebSocket connection to a GARDENA smart Gateway."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        host: str,
        port: int,
        password: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="GARDENA smart local",
        )
        self.host = host
        self.port = port
        self.password = password
        self.uri = URL.build(scheme="wss", host=host, port=port)

        auth_string = f"_:{password}"
        auth_bytes = auth_string.encode("utf-8")
        self.auth_b64 = base64.b64encode(auth_bytes).decode("ascii")

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task[None] | None = None
        self._devices: DeviceMap = DeviceMap({})
        self._ssl_context = get_default_no_verify_context()
        self._msg_queue: asyncio.Queue[str] = asyncio.Queue()
        self._pending_replies: dict[str, asyncio.Future[Reply]] = {}
        self._includable_devices: dict[str, IncludableDeviceInfo] = {}
        self._includable_timeouts: dict[str, asyncio.TimerHandle] = {}
        self._first_connect_result: asyncio.Future[None] | None = None

    @override
    async def _async_update_data(self) -> DeviceMap:
        """Return the current device map (updates are pushed, not polled)."""
        return self._devices

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket to the gateway is currently connected."""
        return self._ws is not None and not self._ws.closed

    async def async_connect(self) -> None:
        """Connect to the gateway, waiting for the first attempt to succeed."""
        self._first_connect_result = self.hass.loop.create_future()
        self._task = self.hass.async_create_background_task(
            self._ws_loop(), "gardena_smart_local_websocket"
        )
        async with asyncio.timeout(15):
            await self._first_connect_result

    async def async_disconnect(self) -> None:
        """Stop the background WebSocket connection loop."""
        for handle in self._includable_timeouts.values():
            handle.cancel()
        self._includable_timeouts.clear()
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _ws_loop(self) -> None:
        """Keep a WebSocket connection to the gateway open, reconnecting on failure."""
        while True:
            reader_task = None
            consumer_task = None
            try:
                _LOGGER.debug("Connecting to GARDENA smart Gateway at %s", self.uri)
                async with (
                    aiohttp.ClientSession() as session,
                    session.ws_connect(
                        self.uri,
                        ssl=self._ssl_context,
                        heartbeat=30,
                        headers={"Authorization": f"Basic {self.auth_b64}"},
                    ) as ws,
                ):
                    self._ws = ws
                    _LOGGER.info("Connected to GARDENA smart Gateway at %s", self.uri)

                    reader_task = self.hass.async_create_background_task(
                        self._ws_reader(ws),
                        "gardena_smart_local_ws_reader",
                    )
                    consumer_task = self.hass.async_create_background_task(
                        self._msg_consumer(),
                        "gardena_smart_local_msg_consumer",
                    )

                    await self._do_discovery()
                    if (
                        self._first_connect_result
                        and not self._first_connect_result.done()
                    ):
                        self._first_connect_result.set_result(None)

                    # Block until either worker exits (disconnect / error), then
                    # re-raise its exception, if any, so we reconnect below.
                    done, _pending = await asyncio.wait(
                        (reader_task, consumer_task),
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for task in done:
                        task.result()
                    _LOGGER.info(
                        "Disconnected from GARDENA smart Gateway, reconnecting"
                    )

            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket loop cancelled")
                break
            except Exception as err:  # noqa: BLE001
                # Must not crash: this loop is the long-running connection supervisor.
                _LOGGER.error("WebSocket error: %s", err)
                if self._first_connect_result and not self._first_connect_result.done():
                    self._first_connect_result.set_exception(err)
                await asyncio.sleep(5)
            finally:
                self._ws = None
                for bg_task in (reader_task, consumer_task):
                    if bg_task and not bg_task.done():
                        bg_task.cancel()
                        with contextlib.suppress(asyncio.CancelledError, Exception):
                            await bg_task
                # Cancel any pending reply futures so waiters don't hang
                for fut in self._pending_replies.values():
                    if not fut.done():
                        fut.cancel()
                self._pending_replies.clear()
                # Let entities re-check availability now that we're disconnected.
                self.async_update_listeners()

    async def _ws_reader(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        """Read raw messages off the WebSocket and queue them for the consumer."""
        async for msg in ws:
            match msg.type:
                case aiohttp.WSMsgType.TEXT:
                    await self._msg_queue.put(msg.data)
                case aiohttp.WSMsgType.BINARY:
                    await self._msg_queue.put(msg.data.decode("utf-8"))
                case aiohttp.WSMsgType.ERROR:
                    _LOGGER.error("WebSocket error: %s", ws.exception())
                    break
                case aiohttp.WSMsgType.CLOSED | aiohttp.WSMsgType.CLOSING:
                    break
        _LOGGER.warning(
            "Connection to GARDENA smart Gateway closed (close code: %s)", ws.close_code
        )

    async def _msg_consumer(self) -> None:
        """Dispatch queued messages to reply futures or the event handler."""
        try:
            while True:
                raw = await self._msg_queue.get()
                try:
                    messages = IngressMessageList.model_validate_json(raw)
                except Exception:  # noqa: BLE001
                    _LOGGER.debug(
                        "Ignoring non-list message from GARDENA smart Gateway: %s", raw
                    )
                    continue

                passthrough: IngressMessageList = IngressMessageList([])
                for msg in messages:
                    if (
                        isinstance(msg, Reply)
                        and msg.request_id in self._pending_replies
                    ):
                        fut = self._pending_replies.pop(msg.request_id)
                        if not fut.done():
                            fut.set_result(msg)
                    else:
                        passthrough.append(msg)

                if passthrough:
                    await self._handle_messages(passthrough)
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception(
                "Message consumer failed, incoming events are no longer processed"
            )
            raise

    async def _do_discovery(self, broadcast: bool = True) -> None:
        """Request discovery from the gateway and update the device map."""
        discovery = build_discovery_obj()
        n = len(list(discovery))
        _LOGGER.debug(
            "Sent discovery request to GARDENA smart Gateway, awaiting %d replies", n
        )

        try:
            replies = await self.send_request(
                "discovery", discovery, wait_for_response_sec=30
            )
        except TimeoutError as err:
            raise RuntimeError(
                f"Timed out waiting for discovery replies from GARDENA smart Gateway (expected {n})"
            ) from err

        devices = await create_devices_from_messages(replies)
        self._update_devices(devices)
        if broadcast:
            self.async_set_updated_data(self._devices)
        _LOGGER.info("Discovery complete, found %d device(s)", len(self._devices))

    async def _handle_messages(self, messages: IngressMessageList) -> None:
        """Apply incoming events to the device map."""
        try:
            _LOGGER.debug("Handling %d message(s)", len(messages))

            updated = False
            for msg in messages:
                if isinstance(msg, Event) and await self._handle_event(msg):
                    updated = True

            if updated:
                self.async_set_updated_data(self._devices)

        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Error handling messages (may be non-critical): %s", err)

    async def _handle_event(self, event: Event) -> bool:
        """Apply a single event to the device map, returning True if it changed."""
        if event.entity.path.object_name == "includable_device":
            await self._handle_includable_event(event)
            return False

        device_id = event.entity.device
        if not device_id:
            _LOGGER.debug("Event does not have device ID, ignoring: %s", event)
            return False

        if (
            event.op == "delete"
            and event.entity.path.object_name is None
            and device_id in self._devices
        ):
            _LOGGER.info("Device %s removed (delete event)", device_id)
            self.async_drop_device(device_id)
            return False

        if device_id not in self._devices:
            return False

        _LOGGER.debug("Updating device %s with event: %s", device_id, event)
        device = self._devices[device_id]
        was_online = device.is_online
        device.update_data(event)
        if device.is_online != was_online:
            _LOGGER.info(
                "Device %s connection status changed: online=%s",
                device_id,
                device.is_online,
            )
        return True

    def _expire_includable(self, instance_id: str) -> None:
        """Drop an includable device whose heartbeat timed out."""
        _LOGGER.debug("Includable device %s heartbeat timed out, removing", instance_id)
        self._includable_devices.pop(instance_id, None)
        self._includable_timeouts.pop(instance_id, None)

    async def _handle_includable_event(self, event: Event) -> None:
        """Track devices reporting themselves as includable."""
        instance_id = event.entity.path.object_instance_id
        if instance_id is None:
            return

        if event.op == "delete":
            handle = self._includable_timeouts.pop(instance_id, None)
            if handle is not None:
                handle.cancel()
            self._includable_devices.pop(instance_id, None)
            _LOGGER.debug("Includable device %s removed (delete event)", instance_id)
            return

        # Reschedule heartbeat timeout on every update
        handle = self._includable_timeouts.pop(instance_id, None)
        if handle is not None:
            handle.cancel()
        self._includable_timeouts[instance_id] = self.hass.loop.call_later(
            INCLUDABLE_DEVICE_HEARTBEAT_TIMEOUT, self._expire_includable, instance_id
        )

        if instance_id in self._includable_devices:
            _LOGGER.debug(
                "Includable device %s heartbeat, rescheduled timeout", instance_id
            )
            return

        service = event.entity.service
        if service is None:
            return

        identifier = event.payload.get("identifier", {}).get("vs")
        if identifier is None:
            _LOGGER.debug(
                "Includable event for %s lacks identifier, ignoring", instance_id
            )
            return
        try:
            sgtin = SGTIN96Info.from_hex(identifier)
        except ValueError:
            _LOGGER.debug(
                "Includable device %s has unparsable identifier %s, ignoring",
                instance_id,
                identifier,
            )
            return
        device_name = f"{await sgtin.get_model_name()} {sgtin.serial:08d}"

        self._includable_devices[instance_id] = IncludableDeviceInfo(
            instance_id=instance_id,
            service=service,
            device_id=identifier,
            device_name=device_name,
        )
        _LOGGER.info(
            "Discovered includable device: %s (%s, instance %s)",
            identifier,
            device_name,
            instance_id,
        )

    @property
    def includable_devices(self) -> dict[str, IncludableDeviceInfo]:
        """Return the devices currently discovered in inclusion mode."""
        return dict(self._includable_devices)

    async def async_include_device(self, instance_id: str) -> str | None:
        """Include a discovered device and return its device id on success."""
        info = self._includable_devices.get(instance_id)
        if info is None:
            _LOGGER.error("No includable device with instance_id %s", instance_id)
            return None
        device_id = info.device_id

        request = build_inclusion_obj(info.service, instance_id)
        try:
            replies = await self.send_request(
                instance_id, request, wait_for_response_sec=INCLUDE_REPLY_TIMEOUT
            )
        except TimeoutError:
            _LOGGER.error("Timeout waiting for inclusion reply for %s", device_id)
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error including device %s: %s", instance_id, err)
            return None

        for msg in replies:
            if isinstance(msg, Reply) and msg.success:
                for _ in range(INCLUSION_TIMEOUT):
                    if instance_id not in self._includable_devices:
                        break
                    await asyncio.sleep(1)
                else:
                    _LOGGER.error(
                        "Timeout waiting for inclusion to complete for %s", device_id
                    )
                    return None
                _LOGGER.info(
                    "Device %s (instance %s) included successfully",
                    info.device_id,
                    instance_id,
                )
                try:
                    # broadcast=False: the subentry doesn't exist yet at this
                    # point; the caller schedules async_set_updated_data as a
                    # task so it runs after _async_finish_flow adds the subentry.
                    await self._do_discovery(broadcast=False)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Re-discovery after inclusion failed: %s", err)
                    return None
                if info.device_id not in self._devices:
                    _LOGGER.warning(
                        "Included device %s not found in discovery", info.device_id
                    )
                    return None
                return info.device_id

        _LOGGER.error("Inclusion of device %s failed", info.device_id)
        return None

    @callback
    def async_drop_device(self, device_id: str) -> None:
        """Remove a device from the coordinator without contacting the gateway."""
        if self._devices.pop(device_id, None) is not None:
            _LOGGER.debug("Dropped device %s from coordinator", device_id)
            self.async_set_updated_data(self._devices)

    async def async_exclude_device(self, device_id: str) -> bool:
        """Exclude (factory reset) a device from the gateway."""
        device = self._devices.get(device_id)
        if device is None:
            _LOGGER.error("No device with id %s", device_id)
            return False

        request = device.build_exclusion_obj()
        # Drop the device locally before requesting exclusion so the inbound
        # delete event during factory reset cannot resurrect it via
        # downstream listeners (e.g. subentry auto-creation).
        self.async_drop_device(device_id)
        try:
            replies = await self.send_request(
                device_id, request, wait_for_response_sec=EXCLUDE_REPLY_TIMEOUT
            )
        except TimeoutError:
            _LOGGER.error("Timeout waiting for exclusion reply for %s", device_id)
            return False
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error excluding device %s: %s", device_id, err)
            return False

        for msg in replies:
            if isinstance(msg, Reply) and msg.success:
                _LOGGER.info("Device %s excluded successfully", device_id)
                return True

        _LOGGER.error("Exclusion of device %s failed", device_id)
        return False

    def _update_device(self, device: Device) -> None:
        """Add or update a single device in the device map."""
        is_new = device.id not in self._devices
        self._devices[device.id] = device
        if is_new:
            _LOGGER.info(
                "Added new device: %s (%s)", device.id, device.model_definition.name
            )
        else:
            _LOGGER.debug(
                "Updated existing device: %s (%s)",
                device.id,
                device.model_definition.name,
            )

    def _update_devices(self, devices: DeviceMap) -> None:
        """Replace the device map with a fresh, complete discovery result."""
        try:
            for device_id in self._devices.keys() - devices.keys():
                _LOGGER.info(
                    "Device %s no longer present in discovery, dropping", device_id
                )
                del self._devices[device_id]
            for device in devices.values():
                self._update_device(device)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to update devices: %s", err)

    async def send_request(
        self,
        device_id: str,
        request: EgressMessageList,
        wait_for_response_sec: float = 0,
    ) -> IngressMessageList:
        """Send a request to the gateway, optionally waiting for replies."""
        if not self._ws or self._ws.closed:
            raise HomeAssistantError(
                f"Cannot send request to device {device_id}: WebSocket not connected"
            )

        if wait_for_response_sec > 0:
            loop = asyncio.get_running_loop()
            pending_ids = {
                req.request_id for req in request.root if req.request_id is not None
            }
            futures: dict[str, asyncio.Future[Reply]] = {
                rid: loop.create_future() for rid in pending_ids
            }
            self._pending_replies.update(futures)

            await self._ws.send_str(request.model_dump_json())
            _LOGGER.debug("Sent request to device %s: %s", device_id, request)

            try:
                async with asyncio.timeout(wait_for_response_sec):
                    replies = await asyncio.gather(*futures.values())
            except TimeoutError:
                for rid in pending_ids:
                    self._pending_replies.pop(rid, None)
                raise

            return IngressMessageList(list(replies))

        await self._ws.send_str(request.model_dump_json())
        _LOGGER.debug("Sent request to device %s: %s", device_id, request)
        return IngressMessageList([])
