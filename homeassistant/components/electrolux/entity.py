"""Base entity for Electrolux integration."""

from abc import abstractmethod
import logging

from electrolux_group_developer_sdk.client.appliance_client import ApplianceData

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ElectroluxDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class ElectroluxBaseEntity[T: ApplianceData](
    CoordinatorEntity[ElectroluxDataUpdateCoordinator]
):
    """Base class for Electrolux entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        appliance_data: T,
        coordinator: ElectroluxDataUpdateCoordinator,
    ) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)
        appliance_name = appliance_data.appliance.applianceName
        appliance_id = appliance_data.appliance.applianceId
        if appliance_data.details:
            appliance_info = appliance_data.details.applianceInfo

        # Set appliance info
        self._appliance_data = appliance_data
        self._attr_unique_id = f"{appliance_id}"
        self.appliance_id = appliance_id
        self.coordinator = coordinator
        if appliance_data.details:
            self._appliance_capabilities = appliance_data.details.capabilities
        if appliance_data.state:
            self._reported_appliance_state = appliance_data.state.properties.get(
                "reported"
            )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, appliance_id)},
            name=appliance_name,
            manufacturer=appliance_info.brand,
            model=appliance_info.model,
            serial_number=appliance_info.serialNumber,
        )

        self._is_entity_available = True

    @property
    def available(self) -> bool:
        "True if the entity is available."
        return self._is_entity_available

    def set_unavailable(self) -> None:
        """Set entity unavailable."""
        self._is_entity_available = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """When entity is added to HA."""
        await super().async_added_to_hass()
        self.coordinator.async_add_listener(self._handle_coordinator_update)
        self._handle_coordinator_update()

    @abstractmethod
    def _update_attr_state(self) -> None:
        """Update entity-specific attributes."""

    @callback
    def _handle_coordinator_update(self) -> None:
        """When the coordinator updates."""
        appliance_state = self.coordinator.data
        if not appliance_state:
            _LOGGER.warning("Appliance %s not found in update", self.appliance_id)
            return

        # Update state
        self._appliance_data.update_state(appliance_state)
        self._reported_appliance_state = appliance_state.properties.get("reported")
        self._update_attr_state()

        self.async_write_ha_state()
