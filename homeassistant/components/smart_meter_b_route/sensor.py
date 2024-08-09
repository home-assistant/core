"""Smart Meter B Route."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
    ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
    ATTR_API_INSTANTANEOUS_POWER,
    ATTR_API_TOTAL_CONSUMPTION,
    DOMAIN,
)
from .coordinator import BRouteUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = (
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
        name="Instantaneous Current R Phase",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
        name="Instantaneous Current T Phase",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SensorEntityDescription(
        key=ATTR_API_INSTANTANEOUS_POWER,
        name="Instantaneous Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SensorEntityDescription(
        key=ATTR_API_TOTAL_CONSUMPTION,
        name="Total Consumption",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Meter B-route entry."""
    coordinator: BRouteUpdateCoordinator = hass.data[DOMAIN][config.entry_id]

    async_add_entities(
        SmartMeterBRouteSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SmartMeterBRouteSensor(SensorEntity, CoordinatorEntity[BRouteUpdateCoordinator]):
    """Representation of a Smart Meter B-route sensor entity."""

    def __init__(
        self,
        coordinator: BRouteUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize SwitchBot Cloud sensor entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.bid}_{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.data:
            return
        self._attr_native_value = self.coordinator.data.get(self.entity_description.key)
        self.async_write_ha_state()
