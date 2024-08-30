"""Platform for sensor integration."""

from datetime import date
from decimal import Decimal

from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DISPLAY_PRECISION_COP, DISPLAY_PRECISION_WATTS
from .coordinator import WeheatDataUpdateCoordinator
from .entity import WeheatEntity

SENSORS = [
    SensorEntityDescription(
        translation_key="power_output",
        key="power_output",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
    ),
    SensorEntityDescription(
        translation_key="power_input",
        key="power_input",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_WATTS,
    ),
    SensorEntityDescription(
        translation_key="cop",
        key="cop",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=DISPLAY_PRECISION_COP,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors for weheat heat pump."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        WeheatHeatPumpSensor(
            coordinator=coordinator, entity_description=entity_description
        )
        for entity_description in SENSORS
        if hasattr(HeatPump, entity_description.key)
    )


class WeheatHeatPumpSensor(WeheatEntity, SensorEntity):
    """Defines a Weheat heat pump sensor."""

    def __init__(
        self,
        coordinator: WeheatDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self.entity_description = entity_description

        self._attr_unique_id = f"{coordinator.heatpump_id}_{entity_description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_native_value = getattr(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | int | float | date | Decimal:
        """Return the value reported by the sensor and show 0 if not available."""
        if self._attr_native_value is None:
            return Decimal(0)
        return self._attr_native_value
