"""Controller for sharing Omada API coordinators between platforms."""

from functools import partial

from tplink_omada_client.devices import OmadaSwitch, OmadaSwitchPortDetails
from tplink_omada_client.omadasiteclient import OmadaSiteClient

from homeassistant.core import HomeAssistant

from .coordinator import OmadaCoordinator


async def _poll_switch_state(
    client: OmadaSiteClient, network_switch: OmadaSwitch
) -> dict[str, OmadaSwitchPortDetails]:
    """Poll a switch's current state."""
    ports = await client.get_switch_ports(network_switch)
    return {p.port_id: p for p in ports}


class OmadaSiteController:
    """Controller for the Omada SDN site."""

    def __init__(self, hass: HomeAssistant, omada_client: OmadaSiteClient) -> None:
        """Create the controller."""
        self._hass = hass
        self._omada_client = omada_client

        self._switch_port_coordinators: dict[
            str, OmadaCoordinator[OmadaSwitchPortDetails]
        ] = {}

    @property
    def omada_client(self) -> OmadaSiteClient:
        """Get the connected client API for the site to manage."""
        return self._omada_client

    def get_switch_port_coordinator(
        self, switch: OmadaSwitch
    ) -> OmadaCoordinator[OmadaSwitchPortDetails]:
        """Get coordinator for network port information of a given switch."""
        if switch.mac not in self._switch_port_coordinators:
            self._switch_port_coordinators[switch.mac] = OmadaCoordinator[
                OmadaSwitchPortDetails
            ](
                self._hass,
                self._omada_client,
                f"{switch.name} Ports",
                partial(_poll_switch_state, network_switch=switch),
            )

        return self._switch_port_coordinators[switch.mac]
