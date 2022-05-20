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
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt

from . import ValloxDataUpdateCoordinator, ValloxEntity
from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    MODE_ON,
    VALLOX_CELL_STATE_TO_STR,
    VALLOX_PROFILE_TO_STR_REPORTABLE,
)


class ValloxSensor(ValloxEntity, SensorEntity):
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

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{self._device_uuid}-{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        if (metric_key := self.entity_description.metric_key) is None:
            return None

        return self.coordinator.data.get_metric(metric_key)


class ValloxProfileSensor(ValloxSensor):
    """Child class for profile reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        vallox_profile = self.coordinator.data.profile
        return VALLOX_PROFILE_TO_STR_REPORTABLE.get(vallox_profile)


# There is a quirk with respect to the fan speed reporting. The device keeps on reporting the last
# valid fan speed from when the device was in regular operation mode, even if it left that state and
# has been shut off in the meantime.
#
# Therefore, first query the overall state of the device, and report zero percent fan speed in case
# it is not in regular operation mode.
class ValloxFanSpeedSensor(ValloxSensor):
    """Child class for fan speed reporting."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        fan_is_on = self.coordinator.data.get_metric(METRIC_KEY_MODE) == MODE_ON
        return super().native_value if fan_is_on else 0


class ValloxFilterRemainingSensor(ValloxSensor):
    """Child class for filter remaining time reporting."""

    @property
    def native_value(self) -> StateType | datetime:
        """Return the value reported by the sensor."""
        next_filter_change_date = self.coordinator.data.get_next_filter_change_date()

        if next_filter_change_date is None:
            return None

        return datetime.combine(
            next_filter_change_date,
            time(hour=13, minute=0, second=0, tzinfo=dt.DEFAULT_TIME_ZONE),
        )


class ValloxCellStateSensor(ValloxSensor):
    """Child class for cell state reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        super_native_value = super().native_value

        if not isinstance(super_native_value, int):
            return None

        return VALLOX_CELL_STATE_TO_STR.get(super_native_value)


@dataclass
class ValloxSensorEntityDescription(SensorEntityDescription):
    """Describes Vallox sensor entity."""

    metric_key: str | None = None
    sensor_type: type[ValloxSensor] = ValloxSensor


SENSORS: tuple[ValloxSensorEntityDescription, ...] = (
    ValloxSensorEntityDescription(
        key="current_profile",
        name="Current Profile",
        icon="mdi:gauge",
        sensor_type=ValloxProfileSensor,
    ),
    ValloxSensorEntityDescription(
        key="fan_speed",
        name="Fan Speed",
        metric_key="A_CYC_FAN_SPEED",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        sensor_type=ValloxFanSpeedSensor,
    ),
    ValloxSensorEntityDescription(
        key="remaining_time_for_filter",
        name="Remaining Time For Filter",
        device_class=SensorDeviceClass.TIMESTAMP,
        sensor_type=ValloxFilterRemainingSensor,
    ),
    ValloxSensorEntityDescription(
        key="cell_state",
        name="Cell State",
        icon="mdi:swap-horizontal-bold",
        metric_key="A_CYC_CELL_STATE",
        sensor_type=ValloxCellStateSensor,
    ),
    ValloxSensorEntityDescription(
        key="extract_air",
        name="Extract Air",
        metric_key="A_CYC_TEMP_EXTRACT_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="exhaust_air",
        name="Exhaust Air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="outdoor_air",
        name="Outdoor Air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_air",
        name="Supply Air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="humidity",
        name="Humidity",
        metric_key="A_CYC_RH_VALUE",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ValloxSensorEntityDescription(
        key="efficiency",
        name="Efficiency",
        metric_key="A_CYC_EXTRACT_EFFICIENCY",
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ValloxSensorEntityDescription(
        key="co2",
        name="CO2",
        metric_key="A_CYC_CO2_VALUE",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    name = hass.data[DOMAIN][entry.entry_id]["name"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            description.sensor_type(name, coordinator, description)
            for description in SENSORS
        ]
    )
