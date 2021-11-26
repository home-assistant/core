"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.wallbox import WallboxCoordinator, WallboxData
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    LENGTH_KILOMETERS,
    PERCENTAGE,
    POWER_KILO_WATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ADDED_ENERGY_KEY,
    CONF_ADDED_RANGE_KEY,
    CONF_CHARGING_POWER_KEY,
    CONF_CHARGING_SPEED_KEY,
    CONF_COST_KEY,
    CONF_CURRENT_MODE_KEY,
    CONF_DEPOT_PRICE_KEY,
    CONF_MAX_AVAILABLE_POWER_KEY,
    CONF_MAX_CHARGING_CURRENT_KEY,
    CONF_STATE_OF_CHARGE_KEY,
    CONF_STATUS_DESCRIPTION_KEY,
    DOMAIN,
)

CONF_STATION = "station"
UPDATE_INTERVAL = 30


@dataclass
class WallboxRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[WallboxData], int | float | str]


@dataclass
class WallboxSensorEntityDescription(SensorEntityDescription, WallboxRequiredKeysMixin):
    """Describes Wallbox sensor entity."""


SENSOR_TYPES: dict[str, WallboxSensorEntityDescription] = {
    CONF_CHARGING_POWER_KEY: WallboxSensorEntityDescription(
        key=CONF_CHARGING_POWER_KEY,
        name="Charging Power",
        native_unit_of_measurement=POWER_KILO_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=lambda data: round(data[CONF_CHARGING_POWER_KEY], 2),
    ),
    CONF_MAX_AVAILABLE_POWER_KEY: WallboxSensorEntityDescription(
        key=CONF_MAX_AVAILABLE_POWER_KEY,
        name="Max Available Power",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=lambda data: round(data[CONF_MAX_AVAILABLE_POWER_KEY], 0),
    ),
    CONF_CHARGING_SPEED_KEY: WallboxSensorEntityDescription(
        key=CONF_CHARGING_SPEED_KEY,
        icon="mdi:speedometer",
        name="Charging Speed",
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=lambda data: round(data[CONF_CHARGING_SPEED_KEY], 0),
    ),
    CONF_ADDED_RANGE_KEY: WallboxSensorEntityDescription(
        key=CONF_ADDED_RANGE_KEY,
        icon="mdi:map-marker-distance",
        name="Added Range",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        value_fn=lambda data: round(data[CONF_ADDED_RANGE_KEY], 0),
    ),
    CONF_ADDED_ENERGY_KEY: WallboxSensorEntityDescription(
        key=CONF_ADDED_ENERGY_KEY,
        name="Added Energy",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        value_fn=lambda data: round(data[CONF_ADDED_ENERGY_KEY], 2),
    ),
    CONF_COST_KEY: WallboxSensorEntityDescription(
        key=CONF_COST_KEY,
        icon="mdi:ev-station",
        name="Cost",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        value_fn=lambda data: data[CONF_COST_KEY],
    ),
    CONF_STATE_OF_CHARGE_KEY: WallboxSensorEntityDescription(
        key=CONF_STATE_OF_CHARGE_KEY,
        name="State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=lambda data: data[CONF_STATE_OF_CHARGE_KEY],
    ),
    CONF_CURRENT_MODE_KEY: WallboxSensorEntityDescription(
        key=CONF_CURRENT_MODE_KEY,
        icon="mdi:ev-station",
        name="Current Mode",
        value_fn=lambda data: data[CONF_CURRENT_MODE_KEY],
    ),
    CONF_DEPOT_PRICE_KEY: WallboxSensorEntityDescription(
        key=CONF_DEPOT_PRICE_KEY,
        icon="mdi:ev-station",
        name="Depot Price",
        value_fn=lambda data: round(data[CONF_DEPOT_PRICE_KEY], 2),
    ),
    CONF_STATUS_DESCRIPTION_KEY: WallboxSensorEntityDescription(
        key=CONF_STATUS_DESCRIPTION_KEY,
        icon="mdi:ev-station",
        name="Status Description",
        value_fn=lambda data: data[CONF_STATUS_DESCRIPTION_KEY],
    ),
    CONF_MAX_CHARGING_CURRENT_KEY: WallboxSensorEntityDescription(
        key=CONF_MAX_CHARGING_CURRENT_KEY,
        name="Max. Charging Current",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=DEVICE_CLASS_CURRENT,
        state_class=STATE_CLASS_MEASUREMENT,
        value_fn=lambda data: data[CONF_MAX_CHARGING_CURRENT_KEY],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox sensor entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            WallboxSensor(coordinator, entry, description)
            for ent in coordinator.data
            if (description := SENSOR_TYPES.get(ent))
        ]
    )


class WallboxSensor(CoordinatorEntity, SensorEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSensorEntityDescription
    coordinator: WallboxCoordinator

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        entry: ConfigEntry,
        description: WallboxSensorEntityDescription,
    ) -> None:
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_name = f"{entry.title} {description.name}"

    @property
    def native_value(self) -> int | float | str:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
