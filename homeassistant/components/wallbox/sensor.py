"""Home Assistant component for accessing the Wallbox Portal API. The sensor component creates multiple sensors regarding wallbox performance."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CHARGER_ADDED_DISCHARGED_ENERGY_KEY,
    CHARGER_ADDED_ENERGY_KEY,
    CHARGER_ADDED_RANGE_KEY,
    CHARGER_CHARGING_POWER_KEY,
    CHARGER_CHARGING_SPEED_KEY,
    CHARGER_COST_KEY,
    CHARGER_CURRENCY_KEY,
    CHARGER_CURRENT_MODE_KEY,
    CHARGER_DATA_KEY,
    CHARGER_DEPOT_PRICE_KEY,
    CHARGER_ENERGY_PRICE_KEY,
    CHARGER_MAX_AVAILABLE_POWER_KEY,
    CHARGER_MAX_CHARGING_CURRENT_KEY,
    CHARGER_SERIAL_NUMBER_KEY,
    CHARGER_STATE_OF_CHARGE_KEY,
    CHARGER_STATUS_DESCRIPTION_KEY,
    DOMAIN,
)
from .coordinator import WallboxCoordinator
from .entity import WallboxEntity

CHARGER_STATION = "station"
UPDATE_INTERVAL = 30

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WallboxSensorEntityDescription(SensorEntityDescription):
    """Describes Wallbox sensor entity."""

    precision: int | None = None


SENSOR_TYPES: dict[str, WallboxSensorEntityDescription] = {
    CHARGER_CHARGING_POWER_KEY: WallboxSensorEntityDescription(
        key=CHARGER_CHARGING_POWER_KEY,
        translation_key=CHARGER_CHARGING_POWER_KEY,
        precision=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_MAX_AVAILABLE_POWER_KEY: WallboxSensorEntityDescription(
        key=CHARGER_MAX_AVAILABLE_POWER_KEY,
        translation_key=CHARGER_MAX_AVAILABLE_POWER_KEY,
        precision=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_CHARGING_SPEED_KEY: WallboxSensorEntityDescription(
        key=CHARGER_CHARGING_SPEED_KEY,
        translation_key=CHARGER_CHARGING_SPEED_KEY,
        precision=0,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_ADDED_RANGE_KEY: WallboxSensorEntityDescription(
        key=CHARGER_ADDED_RANGE_KEY,
        translation_key=CHARGER_ADDED_RANGE_KEY,
        precision=0,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    CHARGER_ADDED_ENERGY_KEY: WallboxSensorEntityDescription(
        key=CHARGER_ADDED_ENERGY_KEY,
        translation_key=CHARGER_ADDED_ENERGY_KEY,
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    CHARGER_ADDED_DISCHARGED_ENERGY_KEY: WallboxSensorEntityDescription(
        key=CHARGER_ADDED_DISCHARGED_ENERGY_KEY,
        translation_key=CHARGER_ADDED_DISCHARGED_ENERGY_KEY,
        precision=2,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    CHARGER_COST_KEY: WallboxSensorEntityDescription(
        key=CHARGER_COST_KEY,
        translation_key=CHARGER_COST_KEY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    CHARGER_STATE_OF_CHARGE_KEY: WallboxSensorEntityDescription(
        key=CHARGER_STATE_OF_CHARGE_KEY,
        translation_key=CHARGER_STATE_OF_CHARGE_KEY,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_CURRENT_MODE_KEY: WallboxSensorEntityDescription(
        key=CHARGER_CURRENT_MODE_KEY,
        translation_key=CHARGER_CURRENT_MODE_KEY,
    ),
    CHARGER_DEPOT_PRICE_KEY: WallboxSensorEntityDescription(
        key=CHARGER_DEPOT_PRICE_KEY,
        translation_key=CHARGER_DEPOT_PRICE_KEY,
        precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_ENERGY_PRICE_KEY: WallboxSensorEntityDescription(
        key=CHARGER_ENERGY_PRICE_KEY,
        translation_key=CHARGER_ENERGY_PRICE_KEY,
        precision=2,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    CHARGER_STATUS_DESCRIPTION_KEY: WallboxSensorEntityDescription(
        key=CHARGER_STATUS_DESCRIPTION_KEY,
        translation_key=CHARGER_STATUS_DESCRIPTION_KEY,
    ),
    CHARGER_MAX_CHARGING_CURRENT_KEY: WallboxSensorEntityDescription(
        key=CHARGER_MAX_CHARGING_CURRENT_KEY,
        translation_key=CHARGER_MAX_CHARGING_CURRENT_KEY,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create wallbox sensor entities in HASS."""
    coordinator: WallboxCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        WallboxSensor(coordinator, description)
        for ent in coordinator.data
        if (description := SENSOR_TYPES.get(ent))
    )


class WallboxSensor(WallboxEntity, SensorEntity):
    """Representation of the Wallbox portal."""

    entity_description: WallboxSensorEntityDescription

    def __init__(
        self,
        coordinator: WallboxCoordinator,
        description: WallboxSensorEntityDescription,
    ) -> None:
        """Initialize a Wallbox sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{description.key}-{coordinator.data[CHARGER_DATA_KEY][CHARGER_SERIAL_NUMBER_KEY]}"

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor. Round the value when it, and the precision property are not None."""
        if (
            sensor_round := self.entity_description.precision
        ) is not None and self.coordinator.data[
            self.entity_description.key
        ] is not None:
            return cast(
                StateType,
                round(self.coordinator.data[self.entity_description.key], sensor_round),
            )
        return cast(StateType, self.coordinator.data[self.entity_description.key])

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of the sensor. When monetary, get the value from the api."""
        if self.entity_description.key in (
            CHARGER_ENERGY_PRICE_KEY,
            CHARGER_DEPOT_PRICE_KEY,
        ):
            return cast(str, self.coordinator.data[CHARGER_CURRENCY_KEY])
        return cast(str, self.entity_description.native_unit_of_measurement)
