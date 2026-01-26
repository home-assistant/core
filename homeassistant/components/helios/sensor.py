"""Support for Helios ventilation unit sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from . import HeliosConfigEntry
from .const import (
    METRIC_KEY_MODE,
    MODE_ON,
    HELIOS_CELL_STATE_TO_STR,
    HELIOS_PROFILE_TO_PRESET_MODE,
)
from .coordinator import HeliosDataUpdateCoordinator
from .entity import HeliosEntity


class HeliosSensorEntity(HeliosEntity, SensorEntity):
    """Representation of a Helios sensor."""

    entity_description: HeliosSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: HeliosDataUpdateCoordinator,
        description: HeliosSensorEntityDescription,
    ) -> None:
        """Initialize the Helios sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_unique_id = f"{self._device_uuid}-{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        if (metric_key := self.entity_description.metric_key) is None:
            return None

        value = self.coordinator.data.get(metric_key)

        if self.entity_description.round_ndigits is not None and isinstance(
            value, float
        ):
            value = round(value, self.entity_description.round_ndigits)

        return value


class HeliosProfileSensor(HeliosSensorEntity):
    """Child class for profile reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        helios_profile = self.coordinator.data.profile
        return HELIOS_PROFILE_TO_PRESET_MODE.get(helios_profile)


class HeliosFanSpeedSensor(HeliosSensorEntity):
    """Child class for fan speed reporting."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        fan_is_on = self.coordinator.data.get(METRIC_KEY_MODE) == MODE_ON
        return super().native_value if fan_is_on else 0


class HeliosFilterRemainingSensor(HeliosSensorEntity):
    """Child class for filter remaining time reporting."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        next_filter_change_date = self.coordinator.data.next_filter_change_date

        if next_filter_change_date is None:
            return None

        return datetime.combine(
            next_filter_change_date,
            time(hour=13, minute=0, second=0, tzinfo=dt_util.get_default_time_zone()),
        )


class HeliosCellStateSensor(HeliosSensorEntity):
    """Child class for cell state reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        super_native_value = super().native_value

        if not isinstance(super_native_value, int):
            return None

        return HELIOS_CELL_STATE_TO_STR.get(super_native_value)


class HeliosProfileDurationSensor(HeliosSensorEntity):
    """Child class for profile duration reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""

        return self.coordinator.data.get_remaining_profile_duration(
            self.coordinator.data.profile
        )


@dataclass(frozen=True)
class HeliosSensorEntityDescription(SensorEntityDescription):
    """Describes Helios sensor entity."""

    metric_key: str | None = None
    entity_type: type[HeliosSensorEntity] = HeliosSensorEntity
    round_ndigits: int | None = None


SENSOR_ENTITIES: tuple[HeliosSensorEntityDescription, ...] = (
    # Diagnostic sensors for Diagnostics Box
    HeliosSensorEntityDescription(
        key="current_profile",
        translation_key="current_profile",
        entity_type=HeliosProfileSensor,
    ),
    HeliosSensorEntityDescription(
        key="cell_state",
        translation_key="cell_state",
        metric_key="A_CYC_CELL_STATE",
        entity_type=HeliosCellStateSensor,
    ),
    HeliosSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        metric_key="A_CYC_FAN_SPEED",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_type=HeliosFanSpeedSensor,
    ),
    HeliosSensorEntityDescription(
        key="remaining_time_for_filter",
        translation_key="remaining_time_for_filter",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_type=HeliosFilterRemainingSensor,
    ),
    HeliosSensorEntityDescription(
        key="extract_air",
        translation_key="extract_air",
        metric_key="A_CYC_TEMP_EXTRACT_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeliosSensorEntityDescription(
        key="exhaust_air",
        translation_key="exhaust_air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeliosSensorEntityDescription(
        key="outdoor_air",
        translation_key="outdoor_air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeliosSensorEntityDescription(
        key="supply_air",
        translation_key="supply_air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeliosSensorEntityDescription(
        key="supply_cell_air",
        translation_key="supply_cell_air",
        metric_key="A_CYC_TEMP_SUPPLY_CELL_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeliosSensorEntityDescription(
        key="humidity",
        metric_key="A_CYC_RH_VALUE",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    HeliosSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        metric_key="A_CYC_EXTRACT_EFFICIENCY",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        round_ndigits=0,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeliosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data

    async_add_entities(
        description.entity_type(coordinator, description)
        for description in SENSOR_ENTITIES
    )
