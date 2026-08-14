"""Base class for HDFury entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import HDFuryCoordinator


class HDFuryEntity(CoordinatorEntity[HDFuryCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: HDFuryCoordinator, entity_description: EntityDescription
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = (
            f"{coordinator.data.board['serial']}_{entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            name=f"HDFury {coordinator.data.board['hostname']}",
            manufacturer="HDFury",
            model=coordinator.data.board["hostname"].split("-")[0],
            serial_number=coordinator.data.board["serial"],
            sw_version=coordinator.data.board["version"].removeprefix("FW: "),
            hw_version=coordinator.data.board.get("pcbv"),
            configuration_url=f"http://{coordinator.host}",
            connections={
                (dr.CONNECTION_NETWORK_MAC, coordinator.data.config["macaddr"])
            },
        )
