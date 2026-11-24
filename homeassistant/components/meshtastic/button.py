"""Support for Meshtastic buttons.

The node buttons ask a mesh node for data it already publishes on its own
schedule: a position, a telemetry sample or its user record.  None of them
changes anything on the node, so pressing one twice is harmless.

The gateway's restart button is the one destructive action here.  The firmware
answers ``reboot_seconds`` with a routing acknowledgement and then reboots after
the requested delay, without closing the TCP connection first, so the button
opens the client's reboot grace window as soon as the acknowledgement arrives.
That keeps the entities available across the gap instead of flapping, and it is
also the guard that stops a second press while the node is already on its way
down.
"""

from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .client import raise_for_result
from .config_entity import REBOOT_DELAY_SECONDS, async_send_admin
from .const import (
    DOMAIN,
    PORTNUM_NODEINFO_APP,
    PORTNUM_POSITION_APP,
    PORTNUM_TELEMETRY_APP,
)
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticEntity, MeshtasticNodeEntity
from .models import MeshtasticNode, RequestKind

# Every press goes to the radio, which serves one request at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MeshtasticNodeButtonEntityDescription(ButtonEntityDescription):
    """Describes a request this integration can send to one mesh node."""

    #: Portnum of the empty request packet; the node answers on the same port.
    portnum: int


NODE_BUTTONS: tuple[MeshtasticNodeButtonEntityDescription, ...] = (
    MeshtasticNodeButtonEntityDescription(
        key="request_position",
        translation_key="request_position",
        portnum=PORTNUM_POSITION_APP,
    ),
    MeshtasticNodeButtonEntityDescription(
        key="request_telemetry",
        translation_key="request_telemetry",
        portnum=PORTNUM_TELEMETRY_APP,
    ),
    MeshtasticNodeButtonEntityDescription(
        key="request_node_info",
        translation_key="request_node_info",
        portnum=PORTNUM_NODEINFO_APP,
        entity_registry_enabled_default=False,
    ),
)

RESTART_BUTTON = ButtonEntityDescription(
    key="restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([MeshtasticRestartButton(coordinator)])

    known: set[str] = set()

    @callback
    def _check_nodes() -> None:
        """Add request buttons for every mesh node that introduced itself."""
        new = {
            node_id
            for node_id, node in coordinator.data.nodes.items()
            if node_id not in known
            and not node.presumptive
            and node.num != coordinator.gateway.node_num
        }
        if not new:
            return
        known.update(new)
        async_add_entities(
            MeshtasticNodeRequestButton(
                coordinator, coordinator.data.nodes[node_id], description
            )
            for node_id in new
            for description in NODE_BUTTONS
        )

    _check_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_check_nodes))


class MeshtasticRestartButton(MeshtasticEntity, ButtonEntity):
    """Restart the gateway node."""

    def __init__(self, coordinator: MeshtasticCoordinator) -> None:
        """Initialise the restart button."""
        super().__init__(coordinator, RESTART_BUTTON.key)
        self.entity_description = RESTART_BUTTON

    @override
    async def async_press(self) -> None:
        """Ask the node to reboot, and expect it to go away for a while."""
        client = self.coordinator.client
        if client.reboot_grace_active:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="reboot_in_progress",
                translation_placeholders={"node": self.coordinator.gateway.name},
            )

        def _send(interface: Any) -> Any:
            return interface.localNode.reboot(REBOOT_DELAY_SECONDS)

        await async_send_admin(self.coordinator, _send)
        # The acknowledgement means the reboot is scheduled, not done: the node
        # keeps talking for the delay it was given and then drops off without
        # closing the socket, so the grace window has to cover that wait too.
        client.async_note_reboot_expected(REBOOT_DELAY_SECONDS)


class MeshtasticNodeRequestButton(MeshtasticNodeEntity, ButtonEntity):
    """Ask one mesh node to send something it already knows."""

    entity_description: MeshtasticNodeButtonEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        node: MeshtasticNode,
        description: MeshtasticNodeButtonEntityDescription,
    ) -> None:
        """Initialise a node request button."""
        super().__init__(coordinator, node, description.key)
        self.entity_description = description

    @override
    async def async_press(self) -> None:
        """Send an empty request packet and wait for the node's answer.

        An empty payload is a valid empty message on all three ports; the
        firmware replies with its own because the packet asks for a response.
        """
        node = self.node
        result = await self.coordinator.client.async_send_data(
            b"",
            portnum=self.entity_description.portnum,
            destination=self.node_num,
            kind=RequestKind.DIRECT_REQUEST,
            want_ack=True,
            want_response=True,
        )
        raise_for_result(result, node=node.name if node else self.node_id)
