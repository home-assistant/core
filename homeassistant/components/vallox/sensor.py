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


class ValloxSensorEntity(ValloxEntity, SensorEntity):
    """Representation of a Vallox sensor."""

    entity_description: ValloxSensorEntityDescription
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True

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

        value = self.coordinator.data.get_metric(metric_key)

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
        return VALLOX_PROFILE_TO_STR_REPORTABLE.get(vallox_profile)


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
        fan_is_on = self.coordinator.data.get_metric(METRIC_KEY_MODE) == MODE_ON
        return super().native_value if fan_is_on else 0


class ValloxFilterRemainingSensor(ValloxSensorEntity):
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


class ValloxCellStateSensor(ValloxSensorEntity):
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
    entity_type: type[ValloxSensorEntity] = ValloxSensorEntity
    round_ndigits: int | None = None


SENSOR_ENTITIES: tuple[ValloxSensorEntityDescription, ...] = (
    ValloxSensorEntityDescription(
        key="current_profile",
        name="Current profile",
        icon="mdi:gauge",
        entity_type=ValloxProfileSensor,
    ),
    ValloxSensorEntityDescription(
        key="fan_speed",
        name="Fan speed",
        metric_key="A_CYC_FAN_SPEED",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_type=ValloxFanSpeedSensor,
    ),
    ValloxSensorEntityDescription(
        key="extract_fan_speed",
        name="Extract fan speed",
        metric_key="A_CYC_EXTR_FAN_SPEED",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="RPM",
        entity_type=ValloxFanSpeedSensor,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="supply_fan_speed",
        name="Supply fan speed",
        metric_key="A_CYC_SUPP_FAN_SPEED",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="RPM",
        entity_type=ValloxFanSpeedSensor,
        entity_registry_enabled_default=False,
    ),
    ValloxSensorEntityDescription(
        key="remaining_time_for_filter",
        name="Remaining time for filter",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_type=ValloxFilterRemainingSensor,
    ),
    ValloxSensorEntityDescription(
        key="cell_state",
        name="Cell state",
        icon="mdi:swap-horizontal-bold",
        metric_key="A_CYC_CELL_STATE",
        entity_type=ValloxCellStateSensor,
    ),
    ValloxSensorEntityDescription(
        key="extract_air",
        name="Extract air",
        metric_key="A_CYC_TEMP_EXTRACT_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="exhaust_air",
        name="Exhaust air",
        metric_key="A_CYC_TEMP_EXHAUST_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="outdoor_air",
        name="Outdoor air",
        metric_key="A_CYC_TEMP_OUTDOOR_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_air",
        name="Supply air",
        metric_key="A_CYC_TEMP_SUPPLY_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="supply_cell_air",
        name="Supply cell air",
        metric_key="A_CYC_TEMP_SUPPLY_CELL_AIR",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
    ),
    ValloxSensorEntityDescription(
        key="optional_air",
        name="Optional air",
        metric_key="A_CYC_TEMP_OPTIONAL",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=TEMP_CELSIUS,
        entity_registry_enabled_default=False,
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
        entity_registry_enabled_default=False,
        round_ndigits=0,
    ),
    ValloxSensorEntityDescription(
        key="co2",
        name="CO2",
        metric_key="A_CYC_CO2_VALUE",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        entity_registry_enabled_default=False,
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
            description.entity_type(name, coordinator, description)
            for description in SENSOR_ENTITIES
        ]
    )
