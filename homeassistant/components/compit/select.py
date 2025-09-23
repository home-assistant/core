"""Select platform for Compit integration."""

from compit_inext_api import Parameter

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER_NAME
from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

SELECT_PARAM_TYPE = "Select"
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CompitConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Compit select sensors from a config entry."""

    coordinator = entry.runtime_data
    climate_entities = []
    for device_id in coordinator.connector.all_devices:
        device = coordinator.connector.get_device(device_id)
        if device:
            climate_entities.extend(
                [
                    CompitSelect(
                        coordinator,
                        device_id,
                        device.definition.name,
                        parameter,
                    )
                    for parameter in device.definition.parameters or []
                    if parameter.type == SELECT_PARAM_TYPE
                ]
            )

    async_add_devices(climate_entities)


class CompitSelect(CoordinatorEntity[CompitDataUpdateCoordinator], SelectEntity):
    """Representation of a Compit select entity."""

    def __init__(
        self,
        coordinator: CompitDataUpdateCoordinator,
        device_id: int,
        device_name: str,
        parameter: Parameter,
    ) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_name = parameter.label
        self._attr_unique_id = f"{device_id}_{parameter.parameter_code}"
        self.available_values = {
            detail.description: detail.state
            for detail in parameter.details or []
            if detail is not None
        }
        self._attr_options = list(self.available_values.keys())
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device_id))},
            name=device_name,
            manufacturer=MANUFACTURER_NAME,
            model=device_name,
        )
        self.parameter = parameter

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            super().available
            and self.coordinator.connector.get_device(self.device_id) is not None
        )

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        param = self.coordinator.connector.get_device_parameter(
            self.device_id, self.parameter.parameter_code
        )
        if param is None or param.value is None:
            return None

        for description, state in self.available_values.items():
            if state == param.value:
                return description
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        state_value = self.available_values.get(option)
        if state_value is not None:
            await self.coordinator.connector.set_device_parameter(
                self.device_id, self.parameter.parameter_code, state_value
            )
            self.async_write_ha_state()
