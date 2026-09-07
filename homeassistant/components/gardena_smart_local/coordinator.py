"""Coordinator for a GARDENA smart Gateway."""

from collections.abc import Iterable
import logging
from typing import override

from gardena_smart_local_api.client import (
    DeviceManager,
    IncludableDevice,
    InclusionError,
    RequestError,
)
from gardena_smart_local_api.devices import DeviceMap
from gardena_smart_local_api.devices.irrigation import (
    Gen1IrrigationControl,
    Gen1WaterControl,
    Gen2IrrigationControl,
    Gen2WaterControl,
)
from gardena_smart_local_api.messages import EgressMessageList, IngressMessageList

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

COMMAND_REPLY_TIMEOUT = 10

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
        # The gateway certificate is self-signed, so the manager pins the
        # fingerprint stored when the entry was set up instead of verifying a
        # CA chain. It keeps the connection open, keeps the devices up to date
        # and reconnects on its own.
        self.manager = DeviceManager(
            host,
            port,
            password,
            session=async_get_clientsession(hass),
            fingerprint=fingerprint,
            on_devices_changed=self._on_devices_changed,
            on_disconnect=self._on_disconnect,
            on_auth_failed=self._on_auth_failed,
        )

    @override
    async def _async_update_data(self) -> DeviceMap:
        """Return the current device map (updates are pushed, not polled)."""
        return self.manager.devices

    @property
    def uri(self) -> str:
        """Return the WebSocket URI of the gateway."""
        return self.manager.client.uri

    @property
    def connected(self) -> bool:
        """Return True if the WebSocket to the gateway is currently connected."""
        return self.manager.connected

    @property
    def includable_devices(self) -> dict[str, IncludableDevice]:
        """Return the supported devices currently in inclusion mode."""
        return {
            instance_id: info
            for instance_id, info in self.manager.includable_devices.items()
            if issubclass(info.device_class, SUPPORTED_DEVICE_CLASSES)
        }

    async def async_connect(self) -> None:
        """Connect to the gateway, waiting for the first discovery to finish."""
        await self.manager.connect()

    async def async_disconnect(self) -> None:
        """Stop the connection to the gateway."""
        await self.manager.disconnect()

    @callback
    def async_publish_devices(self) -> None:
        """Tell the entities that the devices changed."""
        self.async_set_updated_data(self.manager.devices)

    @callback
    def _on_devices_changed(self, device_ids: Iterable[str]) -> None:
        """Pass the devices the manager changed on to the entities."""
        self.async_publish_devices()

    @callback
    def _on_disconnect(self) -> None:
        """Let entities re-check their availability once the connection drops."""
        self.async_update_listeners()

    @callback
    def _on_auth_failed(self) -> None:
        """Start reauthentication after the gateway rejected the password.

        The manager stops, because retrying would only hammer the gateway; the
        reauth flow reloads the entry.
        """
        self.config_entry.async_start_reauth(self.hass)

    async def async_include_device(self, instance_id: str) -> str | None:
        """Include a device in inclusion mode and return its device id.

        The entities are not told about the new device. The caller does that
        with `async_publish_devices`, once the subentry of the device exists.
        """
        info = self.includable_devices.get(instance_id)
        if info is None:
            _LOGGER.error("No supported includable device with id %s", instance_id)
            return None
        try:
            device = await self.manager.include_device(instance_id, notify=False)
        except InclusionError as err:
            _LOGGER.error("Inclusion of device %s failed: %s", info.device_id, err)
            return None
        return device.id

    async def async_exclude_device(self, device_id: str) -> bool:
        """Exclude (factory reset) a device from the gateway."""
        try:
            await self.manager.exclude_device(device_id)
        except (RequestError, TimeoutError, ConnectionError) as err:
            _LOGGER.error("Exclusion of device %s failed: %s", device_id, err)
            return False
        return True

    async def async_send_command(
        self,
        device_id: str,
        request: EgressMessageList,
        timeout: float = COMMAND_REPLY_TIMEOUT,
    ) -> IngressMessageList:
        """Send a request that changes a device and wait for the replies.

        Raises `RequestError` if the gateway rejects the request, `TimeoutError`
        if it does not answer in time, and `ConnectionError` if the connection
        is not open or drops.
        """
        return await self.manager.send_command(device_id, request, timeout)
