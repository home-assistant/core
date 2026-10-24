"""Base entities for the Meshtastic integration."""

from typing import override

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    gateway_device_id,
    gateway_unique_id,
    node_device_id,
    node_unique_id,
)
from .coordinator import MeshtasticCoordinator
from .models import MeshtasticNode


class MeshtasticEntity(CoordinatorEntity[MeshtasticCoordinator]):
    """Base entity attached to the gateway device.

    Subclasses set ``entity_description`` themselves and pass its ``key`` here,
    so the unique id is built from immutable values only.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: MeshtasticCoordinator, key: str) -> None:
        """Initialise a gateway-scoped entity."""
        super().__init__(coordinator)
        gateway = coordinator.gateway
        self.gateway_num = gateway.node_num
        self._attr_unique_id = gateway_unique_id(gateway.node_num, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, gateway_device_id(gateway.node_num))},
            manufacturer=MANUFACTURER,
            model=gateway.hardware_model,
            name=gateway.name,
            sw_version=gateway.firmware_version,
            serial_number=gateway.node_id,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True when the gateway link is usable.

        A reboot we asked for is not a reason to make every entity go
        unavailable: the node is back within a minute.
        """
        return super().available or self.coordinator.client.reboot_grace_active


class MeshtasticNodeEntity(CoordinatorEntity[MeshtasticCoordinator]):
    """Base entity attached to a mesh-node sub-device of the gateway."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: MeshtasticCoordinator, node: MeshtasticNode, key: str
    ) -> None:
        """Initialise a node-scoped entity."""
        super().__init__(coordinator)
        gateway = coordinator.gateway
        self.gateway_num = gateway.node_num
        self.node_num = node.num
        self.node_id = node.node_id
        self._attr_unique_id = node_unique_id(gateway.node_num, node.num, key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, node_device_id(gateway.node_num, node.num))},
            manufacturer=MANUFACTURER,
            model=node.hardware_model,
            name=node.name,
            serial_number=node.node_id,
            # The gateway device is registered in async_setup_entry, so it
            # always resolves here even if a node entity is added first.
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, gateway_device_id(gateway.node_num)),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
        )

    @property
    def node(self) -> MeshtasticNode | None:
        """Return the current record of this node, if it is still known."""
        return self.coordinator.data.nodes.get(self.node_id)

    @property
    @override
    def available(self) -> bool:
        """Return True when the link is usable and the node is still known."""
        if self.node is None:
            return False
        return super().available or self.coordinator.client.reboot_grace_active
