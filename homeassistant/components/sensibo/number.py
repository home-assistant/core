"""Number platform for Sensibo integration."""

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator

NUMBER_TYPES: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key="calibration_temp",
        name="Temperature calibration",
        icon="mdi:thermometer",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        min_value=-10,
        max_value=10,
        step=1,
    ),
    NumberEntityDescription(
        key="calibration_hum",
        name="Humidity calibration",
        icon="mdi:water",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        min_value=-10,
        max_value=10,
        step=1,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo number platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for description in NUMBER_TYPES:
        for device_id, device_data in coordinator.data.items():
            if device_data["hvac_modes"] and device_data["temp"]:
                entities.append(SensiboNumber(coordinator, device_id, description))
    async_add_entities(entities)


class SensiboNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Sensibo numbers."""

    coordinator: SensiboDataUpdateCoordinator
    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: NumberEntityDescription,
    ) -> None:
        """Initiate Sensibo Number."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id} {entity_description.key}"
        self._attr_name = (
            f"{coordinator.data[device_id]['name']} {entity_description.name}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.data[device_id]["id"])},
            name=coordinator.data[device_id]["name"],
            manufacturer="Sensibo",
            configuration_url="https://home.sensibo.com/",
            model=coordinator.data[device_id]["model"],
            sw_version=coordinator.data[device_id]["fw_ver"],
            hw_version=coordinator.data[device_id]["fw_type"],
            suggested_area=coordinator.data[device_id]["name"],
        )

    @property
    def value(self) -> float:
        """Return the value from coordinator data."""
        return self.coordinator.data[self._device_id][self.entity_description.key]

    def set_value(self, value: float) -> None:
        """Set value not implemented."""
        raise HomeAssistantError("Sensibo does not support setting value")
