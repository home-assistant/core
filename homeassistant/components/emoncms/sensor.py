"""Support for monitoring emoncms feeds."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_URL,
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSoundPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import template
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .config_flow import sensor_name
from .const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    FEED_ID,
    FEED_NAME,
    FEED_TAG,
)
from .coordinator import EmonCMSConfigEntry, EmoncmsCoordinator

SENSORS: dict[str | None, SensorEntityDescription] = {
    "kWh": SensorEntityDescription(
        key="energy|kWh",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "Wh": SensorEntityDescription(
        key="energy|Wh",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "kW": SensorEntityDescription(
        key="power|kW",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "W": SensorEntityDescription(
        key="power|W",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V": SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "A": SensorEntityDescription(
        key="current",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "VA": SensorEntityDescription(
        key="apparent_power",
        translation_key="apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°C": SensorEntityDescription(
        key="temperature|celsius",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "°F": SensorEntityDescription(
        key="temperature|fahrenheit",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "K": SensorEntityDescription(
        key="temperature|kelvin",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "Hz": SensorEntityDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "hPa": SensorEntityDescription(
        key="pressure",
        translation_key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "dB": SensorEntityDescription(
        key="decibel",
        translation_key="decibel",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m³": SensorEntityDescription(
        key="volume|cubic_meter",
        translation_key="volume",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m³/h": SensorEntityDescription(
        key="flow|cubic_meters_per_hour",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "l/m": SensorEntityDescription(
        key="flow|liters_per_minute",
        translation_key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "m/s": SensorEntityDescription(
        key="speed|meters_per_second",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "µg/m³": SensorEntityDescription(
        key="concentration|microgram_per_cubic_meter",
        translation_key="concentration",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ppm": SensorEntityDescription(
        key="concentration|microgram_parts_per_million",
        translation_key="concentration",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "%": SensorEntityDescription(
        key="percent",
        translation_key="percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

ATTR_FEEDID = "FeedId"
ATTR_FEEDNAME = "FeedName"
ATTR_LASTUPDATETIME = "LastUpdated"
ATTR_LASTUPDATETIMESTR = "LastUpdatedStr"
ATTR_SIZE = "Size"
ATTR_TAG = "Tag"
ATTR_USERID = "UserId"
DECIMALS = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EmonCMSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the emoncms sensors."""
    name = sensor_name(entry.data[CONF_URL])
    exclude_feeds = entry.data.get(CONF_EXCLUDE_FEEDID)
    include_only_feeds = entry.options.get(
        CONF_ONLY_INCLUDE_FEEDID, entry.data.get(CONF_ONLY_INCLUDE_FEEDID)
    )

    if exclude_feeds is None and include_only_feeds is None:
        return

    coordinator = entry.runtime_data
    # uuid was added in emoncms database 11.5.7
    unique_id = entry.unique_id if entry.unique_id else entry.entry_id
    elems = coordinator.data
    if not elems:
        return
    sensors: list[EmonCmsSensor] = []

    for idx, elem in enumerate(elems):
        if include_only_feeds is not None and elem[FEED_ID] not in include_only_feeds:
            continue
        sensors.append(
            EmonCmsSensor(
                coordinator,
                unique_id,
                elem.get("unit"),
                name,
                idx,
            )
        )
    async_add_entities(sensors)


class EmonCmsSensor(CoordinatorEntity[EmoncmsCoordinator], SensorEntity):
    """Implementation of an Emoncms sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EmoncmsCoordinator,
        unique_id: str,
        unit_of_measurement: str | None,
        name: str,
        idx: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.idx = idx
        elem = {}
        if self.coordinator.data:
            elem = self.coordinator.data[self.idx]
        self._attr_translation_placeholders = {
            "emoncms_details": f"{elem[FEED_TAG]} {elem[FEED_NAME]}",
        }
        self._attr_unique_id = f"{unique_id}-{elem[FEED_ID]}"
        description = SENSORS.get(unit_of_measurement)
        if description is not None:
            self.entity_description = description
        else:
            self._attr_native_unit_of_measurement = unit_of_measurement
            self._attr_name = f"{name} {elem[FEED_NAME]}"
        self._update_attributes(elem)

    def _update_attributes(self, elem: dict[str, Any]) -> None:
        """Update entity attributes."""
        self._attr_extra_state_attributes = {
            ATTR_FEEDID: elem[FEED_ID],
            ATTR_TAG: elem[FEED_TAG],
            ATTR_FEEDNAME: elem[FEED_NAME],
        }
        if elem["value"] is not None:
            self._attr_extra_state_attributes[ATTR_SIZE] = elem["size"]
            self._attr_extra_state_attributes[ATTR_USERID] = elem["userid"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIME] = elem["time"]
            self._attr_extra_state_attributes[ATTR_LASTUPDATETIMESTR] = (
                template.timestamp_local(float(elem["time"]))
            )

        self._attr_native_value = None
        if elem["value"] is not None:
            self._attr_native_value = round(float(elem["value"]), DECIMALS)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data:
            self._update_attributes(data[self.idx])
        super()._handle_coordinator_update()
