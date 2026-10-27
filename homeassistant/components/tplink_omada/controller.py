"""Controller for sharing Omada API coordinators between platforms."""

from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING

from tplink_omada_client import OmadaClient, OmadaSiteClient
from tplink_omada_client.devices import OmadaGateway, OmadaListDevice, OmadaSwitch
from tplink_omada_client.exceptions import OmadaClientException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from . import OmadaConfigEntry

from .coordinator import (
    OmadaClientsCoordinator,
    OmadaControllerStatusCoordinator,
    OmadaControllerUpdateCoordinator,
    OmadaDevicesCoordinator,
    OmadaGatewayCoordinator,
    OmadaSwitchPortCoordinator,
)

_LOGGER = logging.getLogger(__name__)


class OmadaSiteController:
    """Controller for the Omada SDN site."""

    _gateway_coordinator: OmadaGatewayCoordinator | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: OmadaConfigEntry,
        controller_client: OmadaClient,
        omada_client: OmadaSiteClient,
    ) -> None:
        """Create the controller."""
        self._hass = hass
        self._config_entry = config_entry
        self._controller_client = controller_client
        self._omada_client = omada_client

        self._controller_status_coordinator = OmadaControllerStatusCoordinator(
            hass, config_entry, controller_client
        )
        self._controller_update_coordinator = OmadaControllerUpdateCoordinator(
            hass, config_entry, controller_client
        )
        self._switch_port_coordinators: dict[str, OmadaSwitchPortCoordinator] = {}
        self._devices_coordinator = OmadaDevicesCoordinator(
            hass, config_entry, omada_client
        )
        self._clients_coordinator = OmadaClientsCoordinator(
            hass, config_entry, omada_client
        )
        self._device_entity_registrations: list[set[str]] = []

    async def initialize_first_refresh(self) -> None:
        """Initialize the all coordinators, and perform first refresh."""
        await self._controller_status_coordinator.async_config_entry_first_refresh()
        await self._controller_update_coordinator.async_request_refresh()
        await self._devices_coordinator.async_config_entry_first_refresh()

        devices = self._devices_coordinator.data.values()
        gateway = next((d for d in devices if d.type == "gateway"), None)
        if gateway:
            self._gateway_coordinator = OmadaGatewayCoordinator(
                self._hass, self._config_entry, self._omada_client, gateway.mac
            )
            await self._gateway_coordinator.async_config_entry_first_refresh()

        await self.clients_coordinator.async_config_entry_first_refresh()

    async def async_register_device_entities(
        self,
        device_filter: Callable[[OmadaListDevice], bool],
        entity_callback: Callable[[OmadaListDevice], Awaitable[bool]],
    ) -> None:
        """Register entities for devices matching the given filter.

        Allows us to handle newly commissioned devices, and devices that aren't
        currently in a queryable state.

        Args:
            device_filter: Function that returns True if a device should be processed.
            entity_callback: Given a discovered Omada device, creates entities and
                returns True, or returns False when the device is not ready yet.
        """
        # Track which devices have been processed already. A device removed by
        # cleanup is dropped from these sets so it is registered again when it
        # reappears.
        processed_devices: set[str] = set()
        self._device_entity_registrations.append(processed_devices)

        async def _async_register_entities() -> None:
            """Register entities for devices that match the filter."""
            devices_to_process = [
                device
                for device in self._devices_coordinator.data.values()
                if device_filter(device)
                and device.mac not in processed_devices
            ]

            if not devices_to_process:
                return

            for device in devices_to_process:
                mac = device.mac
                # The device list was built before this loop, so recheck: a
                # concurrent task may have reserved the device in the meantime.
                if mac in processed_devices:
                    continue
                # Reserve the device before awaiting so concurrent
                # registrations do not process it twice.
                processed_devices.add(mac)
                try:
                    registered = await entity_callback(device)
                except OmadaClientException as ex:
                    # Expected transient failures are retried on the next update.
                    processed_devices.discard(mac)
                    _LOGGER.debug(
                        "Failed to register entities for Omada device %s: %s",
                        mac,
                        ex,
                    )
                    continue
                if not registered:
                    # The device is not ready (for example no data for it yet);
                    # leave it unprocessed so a later update retries.
                    processed_devices.discard(mac)

        @callback
        def _handle_devices_update() -> None:
            self._config_entry.async_create_task(self._hass, _async_register_entities())

        self._config_entry.async_on_unload(
            self._devices_coordinator.async_add_listener(_handle_devices_update)
        )

        # Call once on initial setup
        await _async_register_entities()

    def _forget_device_registration(self, mac: str) -> None:
        """Drop a device from the registration state so it can be added again."""
        for processed in self._device_entity_registrations:
            processed.discard(mac)

    async def async_remove_device(self, mac: str, device_entry: dr.DeviceEntry) -> None:
        """Remove a device entry and drop its cached coordinator state."""
        self._forget_device_registration(mac)
        gateway_coordinator = self._gateway_coordinator
        if gateway_coordinator is not None and gateway_coordinator.mac == mac:
            gateway_coordinator.invalidate()
        coordinator = self._switch_port_coordinators.pop(mac, None)
        if coordinator is not None:
            await coordinator.async_shutdown()
        dr.async_get(self._hass).async_remove_device(device_entry.id)

    async def async_get_gateway(self, mac: str) -> OmadaGateway | None:
        """Return gateway data, refreshing when the cache does not have it.

        Returns None when the data is unavailable; registration then retries on
        the next device-list update instead of rebuilding entities from stale
        port data.
        """
        coordinator = self._gateway_coordinator
        if coordinator is None:
            return None

        gateway = (coordinator.data or {}).get(mac)
        if gateway is not None:
            return gateway
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            return None
        return (coordinator.data or {}).get(mac)

    @property
    def controller_client(self) -> OmadaClient:
        """Get the connected client API for the Omada Controller."""
        return self._controller_client

    @property
    def omada_client(self) -> OmadaSiteClient:
        """Get the connected client API for the site to manage."""
        return self._omada_client

    def get_switch_port_coordinator(
        self, switch: OmadaSwitch
    ) -> OmadaSwitchPortCoordinator:
        """Get coordinator for network port information of a given switch."""
        mac = switch.mac
        if mac not in self._switch_port_coordinators:
            self._switch_port_coordinators[mac] = OmadaSwitchPortCoordinator(
                self._hass, self._config_entry, self._omada_client, switch
            )

        return self._switch_port_coordinators[mac]

    @property
    def controller_status_coordinator(self) -> OmadaControllerStatusCoordinator:
        """Get the coordinator for the Omada Controller status."""
        return self._controller_status_coordinator

    @property
    def controller_update_coordinator(self) -> OmadaControllerUpdateCoordinator:
        """Get the coordinator for Omada Controller firmware updates."""
        return self._controller_update_coordinator

    @property
    def gateway_coordinator(self) -> OmadaGatewayCoordinator | None:
        """Gets the coordinator for site's gateway, or None if there is no gateway."""
        return self._gateway_coordinator

    @property
    def devices_coordinator(self) -> OmadaDevicesCoordinator:
        """Gets the coordinator for site's devices."""
        return self._devices_coordinator

    @property
    def clients_coordinator(self) -> OmadaClientsCoordinator:
        """Gets the coordinator for site's clients."""
        return self._clients_coordinator
