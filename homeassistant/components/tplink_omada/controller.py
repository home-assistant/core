"""Controller for sharing Omada API coordinators between platforms."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tplink_omada_client import OmadaSiteClient
from tplink_omada_client.devices import OmadaSwitch

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import OmadaConfigEntry

from .coordinator import (
    OmadaClientsCoordinator,
    OmadaDevicesCoordinator,
    OmadaGatewayCoordinator,
    OmadaSwitchPortCoordinator,
)


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

    async def initialize_first_refresh(self) -> None:
        """Initialize the all coordinators, and perform first refresh."""
        await self._devices_coordinator.async_config_entry_first_refresh()

        devices = self._devices_coordinator.data.values()
        gateway = next((d for d in devices if d.type == "gateway"), None)
        if gateway:
            self._gateway_coordinator = OmadaGatewayCoordinator(
                self._hass, self._config_entry, self._omada_client, gateway.mac
            )
            await self._gateway_coordinator.async_config_entry_first_refresh()

        await self.clients_coordinator.async_config_entry_first_refresh()

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
