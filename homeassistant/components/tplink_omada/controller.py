"""Controller for sharing Omada API coordinators between platforms."""

from tplink_omada_client.devices import OmadaSwitch, OmadaSwitchPortDetails
from tplink_omada_client.omadasiteclient import OmadaSiteClient

from homeassistant.core import HomeAssistant

from .coordinator import OmadaCoordinator

POLL_SWITCH_PORT = 300


class OmadaSwitchPortCoordinator(OmadaCoordinator[OmadaSwitchPortDetails]):
    """Coordinator for getting details about ports on a switch."""

    def __init__(
        self,
        hass: HomeAssistant,
        omada_client: OmadaSiteClient,
        network_switch: OmadaSwitch,
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass, omada_client, f"{network_switch.name} Ports", POLL_SWITCH_PORT
        )
        self._network_switch = network_switch

    async def poll_update(self) -> dict[str, OmadaSwitchPortDetails]:
        """Poll a switch's current state."""
        ports = await self.omada_client.get_switch_ports(self._network_switch)
        return {p.port_id: p for p in ports}


class OmadaSiteController:
    """Controller for the Omada SDN site."""

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
