"""Controller for sharing Omada API coordinators between platforms."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import TYPE_CHECKING

from tplink_omada_client import OmadaSiteClient
from tplink_omada_client.devices import OmadaListDevice, OmadaSwitch

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

if TYPE_CHECKING:
    from . import OmadaConfigEntry

from .coordinator import (
    OmadaClientsCoordinator,
    OmadaDevicesCoordinator,
    OmadaGatewayCoordinator,
    OmadaKnownClientsCoordinator,
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
        omada_client: OmadaSiteClient,
    ) -> None:
        """Create the controller."""
        self._hass = hass
        self._config_entry = config_entry
        self._omada_client = omada_client

        self._switch_port_coordinators: dict[str, OmadaSwitchPortCoordinator] = {}
        self._devices_coordinator = OmadaDevicesCoordinator(
            hass, config_entry, omada_client
        )
        self._clients_coordinator = OmadaClientsCoordinator(
            hass, config_entry, omada_client
        )
        self._known_clients_coordinator = OmadaKnownClientsCoordinator(
            hass, config_entry, omada_client
        )
        self._device_entity_registrations: list[set[str]] = []
        self._gateway_coordinator_lock = asyncio.Lock()

    async def initialize_first_refresh(self) -> None:
        """Initialize the all coordinators, and perform first refresh."""
        await self._known_clients_coordinator.async_config_entry_first_refresh()
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
        entity_callback: Callable[[OmadaListDevice], Awaitable[None]],
    ) -> None:
        """Register entities for devices matching the given filter.

        Allows us to handle newly commissioned devices, and devices that aren't
        currently in a queryable state.

        Args:
            device_filter: Function that returns True if a device should be processed.
            entity_callback: Given a discovered Omada device,
                creates entities for that device.
        """
        # Track which devices have been processed already. Devices are marked
        # only after successful entity creation so failed registrations retry
        # on the next device update.
        processed_devices: set[str] = set()
        self._device_entity_registrations.append(processed_devices)

        async def _async_register_entities() -> None:
            """Register entities for devices that match the filter."""
            devices_to_process = [
                device
                for device in self._devices_coordinator.data.values()
                if device_filter(device)
                and dr.format_mac(device.mac) not in processed_devices
            ]

            if not devices_to_process:
                return

            for device in devices_to_process:
                try:
                    await entity_callback(device)
                except HomeAssistantError as ex:
                    # Leave the device unmarked so registration retries on the
                    # next device update.
                    _LOGGER.debug(
                        "Failed to register entities for device %s: %s",
                        device.mac,
                        ex,
                    )
                    continue
                processed_devices.add(dr.format_mac(device.mac))

        @callback
        def _handle_devices_update() -> None:
            self._config_entry.async_create_task(self._hass, _async_register_entities())

        self._config_entry.async_on_unload(
            self._devices_coordinator.async_add_listener(_handle_devices_update)
        )

        # Call once on initial setup
        await _async_register_entities()

    async def async_mark_device_removed(self, mac: str) -> None:
        """Allow entities for a removed device to be re-registered if it reappears."""
        mac = dr.format_mac(mac)
        for processed in self._device_entity_registrations:
            processed.discard(mac)

        for switch_mac, switch_coordinator in list(
            self._switch_port_coordinators.items()
        ):
            if dr.format_mac(switch_mac) == mac:
                del self._switch_port_coordinators[switch_mac]
                await switch_coordinator.async_shutdown()

        async with self._gateway_coordinator_lock:
            coordinator = self._gateway_coordinator
            if coordinator is None or dr.format_mac(coordinator.mac) != mac:
                return
            self._gateway_coordinator = None
            await coordinator.async_shutdown()

    @property
    def omada_client(self) -> OmadaSiteClient:
        """Get the connected client API for the site to manage."""
        return self._omada_client

    def get_switch_port_coordinator(
        self, switch: OmadaSwitch
    ) -> OmadaSwitchPortCoordinator:
        """Get coordinator for network port information of a given switch."""
        if switch.mac not in self._switch_port_coordinators:
            self._switch_port_coordinators[switch.mac] = OmadaSwitchPortCoordinator(
                self._hass, self._config_entry, self._omada_client, switch
            )

        return self._switch_port_coordinators[switch.mac]

    async def async_get_gateway_coordinator(self, mac: str) -> OmadaGatewayCoordinator:
        """Get the gateway coordinator, creating or replacing it for the given MAC."""
        async with self._gateway_coordinator_lock:
            coordinator = self._gateway_coordinator
            if coordinator is None or dr.format_mac(coordinator.mac) != dr.format_mac(
                mac
            ):
                if coordinator is not None:
                    await coordinator.async_shutdown()
                coordinator = OmadaGatewayCoordinator(
                    self._hass, self._config_entry, self._omada_client, mac
                )
                self._gateway_coordinator = coordinator
                await coordinator.async_refresh()
            elif not coordinator.data:
                # Retry a previous failed fetch so registration can recover.
                await coordinator.async_refresh()

            return coordinator

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

    @property
    def known_clients_coordinator(self) -> OmadaKnownClientsCoordinator:
        """Gets the coordinator for all wireless clients known to the controller."""
        return self._known_clients_coordinator
