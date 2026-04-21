"""Common classes and elements for Omnilogic Integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OmniLogicUpdateCoordinator


class OmniLogicEntity(CoordinatorEntity[OmniLogicUpdateCoordinator]):
    """Defines the base OmniLogic entity."""

    def __init__(
        self,
        coordinator: OmniLogicUpdateCoordinator,
        kind: str,
        name: str,
        item_id: tuple,
        icon: str,
    ) -> None:
        """Initialize the OmniLogic Entity."""
        super().__init__(coordinator)

        bow_id = None
        entity_data = coordinator.data[item_id]

        backyard_id = item_id[:2]
        if len(item_id) == 6:
            bow_id = item_id[:4]

        msp_system_id = coordinator.data[backyard_id]["systemId"]
        entity_friendly_name = f"{coordinator.data[backyard_id]['BackyardName']} "
        unique_id = f"{msp_system_id}"

        if bow_id is not None:
            unique_id = f"{unique_id}_{coordinator.data[bow_id]['systemId']}"

            if kind != "Heaters":
                entity_friendly_name = (
                    f"{entity_friendly_name}{coordinator.data[bow_id]['Name']} "
                )
            else:
                entity_friendly_name = f"{entity_friendly_name}{coordinator.data[bow_id]['Operation']['VirtualHeater']['Name']} "

        unique_id = f"{unique_id}_{coordinator.data[item_id]['systemId']}_{kind}"

        if entity_data.get("Name") is not None:
            entity_friendly_name = f"{entity_friendly_name} {entity_data['Name']}"

        entity_friendly_name = f"{entity_friendly_name} {name}"

        unique_id = unique_id.replace(" ", "_")

        self._kind = kind
        self._attr_name = entity_friendly_name
        self._attr_unique_id = unique_id
        self._item_id = item_id
        self._attr_icon = icon
        self._attr_extra_state_attributes = {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, msp_system_id)},
            manufacturer="Hayward",
            model="OmniLogic",
            name=coordinator.data[backyard_id]["BackyardName"],
        )
