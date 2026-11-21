"""Coordinator for the GARDENA smart local gateway."""

import asyncio
import contextlib
from dataclasses import dataclass
import logging
from typing import override

from gardena_smart_local_api.client import GatewayClient, RequestError
from gardena_smart_local_api.devices import Device, DeviceMap, build_inclusion_obj
from gardena_smart_local_api.devices.device_builder import MODEL_NUMBER_MAP
from gardena_smart_local_api.devices.irrigation import (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
)
from gardena_smart_local_api.messages import EgressMessageList, Event
from gardena_smart_local_api.sgtin96 import SGTIN96Info

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

# Device classes this valve-only integration exposes entities for. Discovery
# and inclusion also return sensors, mowers and other classes; those must not
# get a config subentry (it would be empty, and removing it would still run a
# factory reset on the device).
type SupportedDevice = (
    Gen1IrrigationControl | Gen1WaterControl | Gen2IrrigationControl | Gen2WaterControl
)
SUPPORTED_DEVICE_CLASSES: tuple[type[SupportedDevice], ...] = (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
)

INCLUDE_REPLY_TIMEOUT = 10
EXCLUDE_REPLY_TIMEOUT = 10
INCLUDABLE_DEVICE_HEARTBEAT_TIMEOUT = 25
INCLUSION_TIMEOUT = 30
COMMAND_REPLY_TIMEOUT = 10
DISCOVERY_REPLY_TIMEOUT = 30
# A device included outside our own inclusion flow (e.g. via the official
# app while we're already connected) arrives as a burst of ordinary events
# for a device_id we don't know yet. Debounce before re-running discovery so
# one burst triggers one discovery, not one per event.
UNKNOWN_DEVICE_DISCOVERY_DEBOUNCE = 3


@dataclass
class IncludableDeviceInfo:
    """Information about a device discovered in inclusion mode."""

    instance_id: str
    service: str
    device_id: str
    device_name: str
    supported: bool


_LOGGER = logging.getLogger(__name__)


type GardenaSmartLocalConfigEntry = ConfigEntry[GardenaSmartLocalCoordinator]


class GardenaSmartLocalCoordinator(DataUpdateCoordinator[DeviceMap]):
    """Coordinator that maintains the WebSocket connection to a GARDENA smart Gateway."""

    config_entry: GardenaSmartLocalConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GardenaSmartLocalConfigEntry,
        host: str,
        port: int,
        password: str,
        fingerprint: str,
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
        # The gateway certificate is self-signed, so the client pins the
        # fingerprint stored when the entry was set up instead of verifying a
        # CA chain. It keeps the connection open and reconnects on its own.
        self.client = GatewayClient(
            host,
            port,
            password,
            session=async_get_clientsession(hass),
            fingerprint=fingerprint,
            on_connect=self._async_on_connect,
            on_event=self._async_on_event,
            on_disconnect=self._on_disconnect,
            on_auth_failed=self._on_auth_failed,
        )
        self._devices: DeviceMap = DeviceMap({})
        self._includable_devices: dict[str, IncludableDeviceInfo] = {}
        self._includable_timeouts: dict[str, asyncio.TimerHandle] = {}
        self._unknown_device_discovery_handle: asyncio.TimerHandle | None = None
        self._unknown_device_discovery_task: asyncio.Task[None] | None = None
        # Set when an event for an unknown device arrives while a re-discovery
        # is already running, since that run may not see the device.
        self._rediscovery_pending = False
        # Devices this integration is including right now. Their event burst
        # must not trigger the unknown-device auto-discovery, which could
        # create the subentry before the inclusion flow does.
        self._including_device_ids: set[str] = set()
        # Devices being excluded, held back from the device map until the
        # gateway answers so neither a discovery nor an event can bring them
        # (and their subentry) back mid-exclusion.
        self._excluding: dict[str, Device] = {}
        # Counts the exclusions the gateway confirmed, and remembers when each
        # device was excluded. A discovery that started before that holds a
        # snapshot that still lists the device, so it must not bring it back.
        self._exclusion_count = 0
        self._excluded_at: dict[str, int] = {}

    @override
    async def _async_update_data(self) -> DeviceMap:
        """Return the current device map (updates are pushed, not polled)."""
        return self._devices

    @property
    def uri(self) -> str:
        """Return the WebSocket URI of the gateway."""
        return self.client.uri

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket to the gateway is currently connected."""
        return self.client.connected

    async def async_connect(self) -> None:
        """Connect to the gateway, waiting for the first discovery to finish."""
        await self.client.connect()

    async def async_disconnect(self) -> None:
        """Stop the connection to the gateway."""
        for handle in self._includable_timeouts.values():
            handle.cancel()
        self._includable_timeouts.clear()
        if self._unknown_device_discovery_handle is not None:
            self._unknown_device_discovery_handle.cancel()
            self._unknown_device_discovery_handle = None
        self._rediscovery_pending = False
        if self._unknown_device_discovery_task is not None:
            self._unknown_device_discovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._unknown_device_discovery_task
            self._unknown_device_discovery_task = None
        await self.client.disconnect()

    async def _async_on_connect(self) -> None:
        """Discover the devices after every (re)connect.

        The first connect only succeeds once this finishes, so a gateway that
        does not answer discovery fails the setup.
        """
        await self._do_discovery()

    @callback
    def _on_disconnect(self) -> None:
        """Let entities re-check their availability once the connection drops."""
        self.async_update_listeners()

    @callback
    def _on_auth_failed(self) -> None:
        """Start reauthentication after the gateway rejected the password.

        The client stops, because retrying would only hammer the gateway; the
        reauth flow reloads the entry.
        """
        self.config_entry.async_start_reauth(self.hass)

    async def _do_discovery(self, broadcast: bool = True) -> None:
        """Request discovery from the gateway and update the device map."""
        started_at = self._exclusion_count
        devices = await self.client.discover_devices(DISCOVERY_REPLY_TIMEOUT)
        for device_id, excluded_at in self._excluded_at.items():
            if excluded_at > started_at:
                devices.pop(device_id, None)
        self._update_devices(devices)
        if broadcast:
            self.async_set_updated_data(self._devices)
        _LOGGER.info("Discovery complete, found %d device(s)", len(self._devices))

    def _schedule_unknown_device_discovery(self, device_id: str) -> None:
        """Debounce a re-discovery run for a device we don't know yet."""
        if device_id in self._including_device_ids:
            # We are including this device ourselves; async_include_device
            # runs its own discovery. A parallel auto-discovery could create
            # the subentry before the inclusion flow does.
            return
        if self._unknown_device_discovery_handle is not None:
            # A run is already scheduled; a burst of events for the same
            # unknown device must not keep pushing it back indefinitely.
            task = self._unknown_device_discovery_task
            if task is not None and not task.done():
                # The run is already past its request, so it may not see this
                # device; make it schedule one more pass when it finishes.
                self._rediscovery_pending = True
            return
        _LOGGER.debug("Event for unknown device %s, scheduling re-discovery", device_id)
        self._arm_unknown_device_discovery()

    def _arm_unknown_device_discovery(self) -> None:
        """Schedule the debounced re-discovery run."""
        self._unknown_device_discovery_handle = self.hass.loop.call_later(
            UNKNOWN_DEVICE_DISCOVERY_DEBOUNCE,
            self._start_unknown_device_discovery,
        )

    @callback
    def _start_unknown_device_discovery(self) -> None:
        """Run the debounced re-discovery, keeping a handle so it can be cancelled."""
        self._unknown_device_discovery_task = self.hass.async_create_task(
            self._discover_unknown_devices()
        )

    async def _discover_unknown_devices(self) -> None:
        """Re-run discovery to pick up a device included outside our own flow."""
        _LOGGER.info("Re-running discovery to pick up newly included device(s)")
        try:
            await self._do_discovery()
        except Exception as err:  # noqa: BLE001 - best-effort, don't crash the coordinator
            _LOGGER.warning("Re-discovery for unknown device(s) failed: %s", err)
        finally:
            # Keep the marker set until discovery finishes; clearing it earlier
            # lets a continued event burst schedule an overlapping run.
            self._unknown_device_discovery_handle = None
        # Skipped when cancelled: CancelledError propagates past this point.
        if self._rediscovery_pending:
            self._rediscovery_pending = False
            self._arm_unknown_device_discovery()

    async def _async_on_event(self, event: Event) -> None:
        """Apply an event pushed by the gateway to the device map."""
        try:
            updated = await self._handle_event(event)
        except Exception as err:  # noqa: BLE001 - one bad event must not stop the rest
            _LOGGER.warning("Error handling event %s: %s", event, err)
            return
        if updated:
            self.async_set_updated_data(self._devices)

    async def _handle_event(self, event: Event) -> bool:
        """Apply a single event to the device map, returning True if it changed."""
        if event.entity.path.object_name == "includable_device":
            await self._handle_includable_event(event)
            return False

        device_id = event.entity.device
        if not device_id:
            _LOGGER.debug("Event does not have device ID, ignoring: %s", event)
            return False

        if device_id in self._excluding:
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
            if event.op != "delete":
                # A device we don't know yet, e.g. included via the
                # official app while we were already connected. Not a
                # delete op, so it's not just a leftover event for an
                # already-excluded device.
                self._schedule_unknown_device_discovery(device_id)
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

        model_class = MODEL_NUMBER_MAP.get(sgtin.item_reference, Device)
        self._includable_devices[instance_id] = IncludableDeviceInfo(
            instance_id=instance_id,
            service=service,
            device_id=identifier,
            device_name=device_name,
            supported=issubclass(model_class, SUPPORTED_DEVICE_CLASSES),
        )
        _LOGGER.info(
            "Discovered includable device: %s (%s, instance %s)",
            identifier,
            device_name,
            instance_id,
        )

    @property
    def includable_devices(self) -> dict[str, IncludableDeviceInfo]:
        """Return the supported devices currently discovered in inclusion mode."""
        return {
            instance_id: info
            for instance_id, info in self._includable_devices.items()
            if info.supported
        }

    async def async_include_device(self, instance_id: str) -> str | None:
        """Include a discovered device and return its device id on success."""
        info = self._includable_devices.get(instance_id)
        if info is None:
            _LOGGER.error("No includable device with instance_id %s", instance_id)
            return None
        if not info.supported:
            _LOGGER.error(
                "Device %s (%s) is not supported by this integration",
                info.device_id,
                info.device_name,
            )
            return None
        self._including_device_ids.add(info.device_id)
        try:
            return await self._include_device(instance_id, info)
        finally:
            self._including_device_ids.discard(info.device_id)

    async def _include_device(
        self, instance_id: str, info: IncludableDeviceInfo
    ) -> str | None:
        """Run the inclusion handshake and pick the device up via discovery."""
        device_id = info.device_id

        request = build_inclusion_obj(info.service, instance_id)
        try:
            await self.client.send_request(request, INCLUDE_REPLY_TIMEOUT)
        except TimeoutError:
            _LOGGER.error("Timeout waiting for inclusion reply for %s", device_id)
            return None
        except RequestError as err:
            _LOGGER.error("Inclusion of device %s rejected: %s", device_id, err)
            return None
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error including device %s: %s", instance_id, err)
            return None

        for _ in range(INCLUSION_TIMEOUT):
            if instance_id not in self._includable_devices:
                break
            await asyncio.sleep(1)
        # Check once more: the device may have left during the last sleep.
        if instance_id in self._includable_devices:
            _LOGGER.error("Timeout waiting for inclusion to complete for %s", device_id)
            return None
        _LOGGER.info(
            "Device %s (instance %s) included successfully", device_id, instance_id
        )
        try:
            # broadcast=False: the subentry doesn't exist yet at this
            # point; the caller schedules async_set_updated_data as a
            # task so it runs after _async_finish_flow adds the subentry.
            await self._do_discovery(broadcast=False)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Re-discovery after inclusion failed: %s", err)
            return None
        if device_id not in self._devices:
            _LOGGER.warning("Included device %s not found in discovery", device_id)
            return None
        return device_id

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
            # A delete event or a fresh discovery already removed it, e.g.
            # excluded through the official app; nothing left to reject.
            _LOGGER.debug(
                "Device %s already absent, treating exclusion as successful",
                device_id,
            )
            return True

        request = device.build_exclusion_obj()
        # Hold the device back while the gateway factory resets it, so the
        # inbound delete events and any concurrent discovery cannot resurrect
        # it via downstream listeners (e.g. subentry auto-creation).
        self._excluding[device_id] = device
        self.async_drop_device(device_id)
        try:
            excluded = await self._send_exclusion(device_id, request)
        finally:
            self._excluding.pop(device_id, None)

        if excluded:
            self._exclusion_count += 1
            self._excluded_at[device_id] = self._exclusion_count

        if not excluded and device_id not in self._devices:
            # Still paired with the gateway: keep its state.
            self._devices[device_id] = device
            self.async_set_updated_data(self._devices)
        return excluded

    async def _send_exclusion(self, device_id: str, request: EgressMessageList) -> bool:
        """Send the exclusion request and return True if the gateway confirms."""
        try:
            await self.client.send_request(request, EXCLUDE_REPLY_TIMEOUT)
        except TimeoutError:
            _LOGGER.error("Timeout waiting for exclusion reply for %s", device_id)
            return False
        except RequestError as err:
            _LOGGER.error("Exclusion of device %s rejected: %s", device_id, err)
            return False
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error excluding device %s: %s", device_id, err)
            return False

        _LOGGER.info("Device %s excluded successfully", device_id)
        return True

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
        for device_id in self._devices.keys() - devices.keys():
            _LOGGER.info(
                "Device %s no longer present in discovery, dropping", device_id
            )
            del self._devices[device_id]
        for device in devices.values():
            if device.id in self._excluding:
                continue
            try:
                self._update_device(device)
            except Exception:
                _LOGGER.warning("Failed to update device %s", device.id, exc_info=True)
