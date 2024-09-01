"""Controller for sharing Omada API coordinators between platforms."""

from tplink_omada_client import OmadaSiteClient
from tplink_omada_client.devices import OmadaSwitch

from homeassistant.core import HomeAssistant

from .coordinator import (
    OmadaClientsCoordinator,
    OmadaGatewayCoordinator,
    OmadaSwitchPortCoordinator,
)


class OmadaSiteController:
    """Controller for the Omada SDN site."""

    _gateway_coordinator: OmadaGatewayCoordinator | None = None
    _initialized_gateway_coordinator = False
    _clients_coordinator: OmadaClientsCoordinator | None = None

    def __init__(self, hass: HomeAssistant, omada_client: OmadaSiteClient) -> None:
        """Create the controller."""
        self._hass = hass
        self._omada_client = omada_client

        self._switch_port_coordinators: dict[str, OmadaSwitchPortCoordinator] = {}

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
                self._hass, self._omada_client, switch
            )

        return self._switch_port_coordinators[switch.mac]

    async def get_gateway_coordinator(self) -> OmadaGatewayCoordinator | None:
        """Get coordinator for site's gateway, or None if there is no gateway."""
        if not self._initialized_gateway_coordinator:
            self._initialized_gateway_coordinator = True
            devices = await self._omada_client.get_devices()
            gateway = next((d for d in devices if d.type == "gateway"), None)
            if not gateway:
                return None

            self._gateway_coordinator = OmadaGatewayCoordinator(
                self._hass, self._omada_client, gateway.mac
            )

        return self._gateway_coordinator

    def get_clients_coordinator(self) -> OmadaClientsCoordinator:
        """Get coordinator for site's clients."""
        if not self._clients_coordinator:
            self._clients_coordinator = OmadaClientsCoordinator(
                self._hass, self._omada_client
            )

        return self._clients_coordinator
