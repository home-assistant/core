"""Support for Vallox ventilation unit sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ValloxDataUpdateCoordinator
from .const import (
    DOMAIN,
    METRIC_KEY_MODE,
    MODE_ON,
    VALLOX_CELL_STATE_TO_STR,
    VALLOX_PROFILE_TO_STR_REPORTABLE,
)


class ValloxSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Vallox sensor."""

    entity_description: ValloxSensorEntityDescription
    coordinator: ValloxDataUpdateCoordinator

    def __init__(
        self,
        name: str,
        coordinator: ValloxDataUpdateCoordinator,
        description: ValloxSensorEntityDescription,
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(coordinator)

        self.entity_description = description

        self._attr_name = f"{name} {description.name}"

        uuid = self.coordinator.data.get_uuid()
        self._attr_unique_id = f"{uuid}-{description.key}"

    @property
    def native_value(self) -> StateType:
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
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        fan_is_on = self.coordinator.data.get_metric(METRIC_KEY_MODE) == MODE_ON
        return super().native_value if fan_is_on else 0


class ValloxFilterRemainingSensor(ValloxSensor):
    """Child class for filter remaining time reporting."""

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        super_native_value = super().native_value

        if not isinstance(super_native_value, (int, float)):
            return None

        # Since only a delta of days is received from the device, fix the time so the timestamp does
        # not change with every update.
        days_remaining = float(super_native_value)
        days_remaining_delta = timedelta(days=days_remaining)
        now = datetime.utcnow().replace(hour=13, minute=0, second=0, microsecond=0)

        return (now + days_remaining_delta).isoformat()


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
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        sensor_type=ValloxFanSpeedSensor,
    ),
    ValloxSensorEntityDescription(
        key="remaining_time_for_filter",
        name="Remaining Time For Filter",
        metric_key="A_CYC_REMAINING_TIME_FOR_FILTER",
        device_class=DEVICE_CLASS_TIMESTAMP,
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
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="exhaust_air",
        name="Exhaust Air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="outdoor_air",
        name="Outdoor Air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_air",
        name="Supply Air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="humidity",
        name="Humidity",
        metric_key="A_CYC_RH_VALUE",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ValloxSensorEntityDescription(
        key="efficiency",
        name="Efficiency",
        metric_key="A_CYC_EXTRACT_EFFICIENCY",
        icon="mdi:gauge",
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    ValloxSensorEntityDescription(
        key="co2",
        name="CO2",
        metric_key="A_CYC_CO2_VALUE",
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensors."""
    if discovery_info is None:
        return

    name = hass.data[DOMAIN]["name"]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities(
        [
            description.sensor_type(name, coordinator, description)
            for description in SENSORS
        ]
    )
