"""Common classes and elements for Omnilogic Integration."""

from typing import Any

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
        self._name = entity_friendly_name
        self._unique_id = unique_id
        self._item_id = item_id
        self._icon = icon
        self._attrs: dict[str, Any] = {}
        self._msp_system_id = msp_system_id
        self._backyard_name = coordinator.data[backyard_id]["BackyardName"]

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self._unique_id

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self):
        """Return the icon for the entity."""
        return self._icon

    @property
    def extra_state_attributes(self):
        """Return the attributes."""
        return self._attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Define the device as back yard/MSP System."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._msp_system_id)},
            manufacturer="Hayward",
            model="OmniLogic",
            name=self._backyard_name,
        )
