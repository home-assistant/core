"""Support for Vallox ventilation unit sensors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
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

from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    MODE_ON,
    VALLOX_CELL_STATE_TO_STR,
    VALLOX_PROFILE_TO_PRESET_MODE,
)
from .coordinator import ValloxDataUpdateCoordinator
from .entity import ValloxEntity


class ValloxSensorEntity(ValloxEntity, SensorEntity):
    """Representation of a Vallox sensor."""

    entity_description: ValloxSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxSensorEntityDescription,
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(name, coordinator)

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


class ValloxProfileSensor(ValloxSensorEntity):
    """Child class for profile reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        vallox_profile = self.coordinator.data.profile
        return VALLOX_PROFILE_TO_PRESET_MODE.get(vallox_profile)


# There is a quirk with respect to the fan speed reporting. The device keeps on reporting the last
# valid fan speed from when the device was in regular operation mode, even if it left that state and
# has been shut off in the meantime.
#
# Therefore, first query the overall state of the device, and report zero percent fan speed in case
# it is not in regular operation mode.
class ValloxFanSpeedSensor(ValloxSensorEntity):
    """Child class for fan speed reporting."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        fan_is_on = self.coordinator.data.get(METRIC_KEY_MODE) == MODE_ON
        return super().native_value if fan_is_on else 0


class ValloxFilterRemainingSensor(ValloxSensorEntity):
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


class ValloxCellStateSensor(ValloxSensorEntity):
    """Child class for cell state reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        super_native_value = super().native_value

        if not isinstance(super_native_value, int):
            return None

        return VALLOX_CELL_STATE_TO_STR.get(super_native_value)


class ValloxProfileDurationSensor(ValloxSensorEntity):
    """Child class for profile duration reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""

        return self.coordinator.data.get_remaining_profile_duration(
            self.coordinator.data.profile
        )


@dataclass(frozen=True)
class ValloxSensorEntityDescription(SensorEntityDescription):
    """Describes Vallox sensor entity."""

    metric_key: str | None = None
    entity_type: type[ValloxSensorEntity] = ValloxSensorEntity
    round_ndigits: int | None = None


SENSOR_ENTITIES: tuple[ValloxSensorEntityDescription, ...] = (
    ValloxSensorEntityDescription(
        key="current_profile",
        translation_key="current_profile",
        entity_type=ValloxProfileSensor,
    ),
    ValloxSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        metric_key="A_CYC_FAN_SPEED",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_type=ValloxFanSpeedSensor,
    ),
    ValloxSensorEntityDescription(
        key="extract_fan_speed",
        translation_key="extract_fan_speed",
        metric_key="A_CYC_EXTR_FAN_SPEED",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_type=ValloxFanSpeedSensor,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        metric_key="A_CYC_SUPP_FAN_SPEED",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_type=ValloxFanSpeedSensor,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="remaining_time_for_filter",
        translation_key="remaining_time_for_filter",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_type=ValloxFilterRemainingSensor,
    ),
    ValloxSensorEntityDescription(
        key="cell_state",
        translation_key="cell_state",
        metric_key="A_CYC_CELL_STATE",
        entity_type=ValloxCellStateSensor,
    ),
    ValloxSensorEntityDescription(
        key="extract_air",
        translation_key="extract_air",
        metric_key="A_CYC_TEMP_EXTRACT_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="exhaust_air",
        translation_key="exhaust_air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="outdoor_air",
        translation_key="outdoor_air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_air",
        translation_key="supply_air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_cell_air",
        translation_key="supply_cell_air",
        metric_key="A_CYC_TEMP_SUPPLY_CELL_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="optional_air",
        translation_key="optional_air",
        metric_key="A_CYC_TEMP_OPTIONAL",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="humidity",
        metric_key="A_CYC_RH_VALUE",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ValloxSensorEntityDescription(
        key="efficiency",
        translation_key="efficiency",
        metric_key="A_CYC_EXTRACT_EFFICIENCY",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        round_ndigits=0,
    ),
    ValloxSensorEntityDescription(
        key="co2",
        metric_key="A_CYC_CO2_VALUE",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="profile_duration",
        translation_key="profile_duration",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_type=ValloxProfileDurationSensor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        description.entity_type(name, coordinator, description)
        for description in SENSOR_ENTITIES
    )
