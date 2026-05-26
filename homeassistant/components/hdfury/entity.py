"""Base class for HDFury entities."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HDFuryRuntimeData
from .coordinator import HDFuryDataUpdateCoordinator


class HDFuryEntity(CoordinatorEntity[HDFuryDataUpdateCoordinator]):
    """Common elements for all entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HDFuryDataUpdateCoordinator,
        runtime_data: HDFuryRuntimeData,
        entity_description: EntityDescription,
    ) -> None:
        """Initialize the entity."""

        super().__init__(coordinator)

        self.runtime_data = runtime_data
        self.entity_description = entity_description

        board = runtime_data.board
        self._attr_unique_id = f"{board['serial']}_{entity_description.key}"
        self._attr_device_info = DeviceInfo(
            name=f"HDFury {board['hostname']}",
            manufacturer="HDFury",
            model=board["hostname"].split("-")[0],
            serial_number=board["serial"],
            sw_version=board["version"].removeprefix("FW: "),
            hw_version=board.get("pcbv"),
            configuration_url=f"http://{runtime_data.host}",
            connections={
                (
                    dr.CONNECTION_NETWORK_MAC,
                    runtime_data.config_coordinator.data["macaddr"],
                )
            },
        )
