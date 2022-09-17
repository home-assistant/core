"""Support for MySensors sensors."""
from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONDUCTIVITY,
    DEGREE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_MILLIVOLT,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    FREQUENCY_HERTZ,
    LENGTH_METERS,
    LIGHT_LUX,
    MASS_KILOGRAMS,
    PERCENTAGE,
    POWER_VOLT_AMPERE,
    POWER_WATT,
    SOUND_PRESSURE_DB,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_CUBIC_METERS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import mysensors
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .helpers import on_unload

SENSORS: dict[str, SensorEntityDescription] = {
    "V_TEMP": SensorEntityDescription(
        key="V_TEMP",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_HUM": SensorEntityDescription(
        key="V_HUM",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_DIMMER": SensorEntityDescription(
        key="V_DIMMER",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
    "V_PERCENTAGE": SensorEntityDescription(
        key="V_PERCENTAGE",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
    ),
    "V_PRESSURE": SensorEntityDescription(
        key="V_PRESSURE",
        icon="mdi:gauge",
    ),
    "V_FORECAST": SensorEntityDescription(
        key="V_FORECAST",
        icon="mdi:weather-partly-cloudy",
    ),
    "V_RAIN": SensorEntityDescription(
        key="V_RAIN",
        icon="mdi:weather-rainy",
    ),
    "V_RAINRATE": SensorEntityDescription(
        key="V_RAINRATE",
        icon="mdi:weather-rainy",
    ),
    "V_WIND": SensorEntityDescription(
        key="V_WIND",
        icon="mdi:weather-windy",
    ),
    "V_GUST": SensorEntityDescription(
        key="V_GUST",
        icon="mdi:weather-windy",
    ),
    "V_DIRECTION": SensorEntityDescription(
        key="V_DIRECTION",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass",
    ),
    "V_WEIGHT": SensorEntityDescription(
        key="V_WEIGHT",
        native_unit_of_measurement=MASS_KILOGRAMS,
        icon="mdi:weight-kilogram",
    ),
    "V_DISTANCE": SensorEntityDescription(
        key="V_DISTANCE",
        native_unit_of_measurement=LENGTH_METERS,
        icon="mdi:ruler",
    ),
    "V_IMPEDANCE": SensorEntityDescription(
        key="V_IMPEDANCE",
        native_unit_of_measurement="ohm",
    ),
    "V_WATT": SensorEntityDescription(
        key="V_WATT",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_KWH": SensorEntityDescription(
        key="V_KWH",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "V_LIGHT_LEVEL": SensorEntityDescription(
        key="V_LIGHT_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:white-balance-sunny",
    ),
    "V_FLOW": SensorEntityDescription(
        key="V_FLOW",
        native_unit_of_measurement=LENGTH_METERS,
        icon="mdi:gauge",
    ),
    "V_VOLUME": SensorEntityDescription(
        key="V_VOLUME",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
    ),
    "V_LEVEL_S_SOUND": SensorEntityDescription(
        key="V_LEVEL_S_SOUND",
        native_unit_of_measurement=SOUND_PRESSURE_DB,
        icon="mdi:volume-high",
    ),
    "V_LEVEL_S_VIBRATION": SensorEntityDescription(
        key="V_LEVEL_S_VIBRATION",
        native_unit_of_measurement=FREQUENCY_HERTZ,
    ),
    "V_LEVEL_S_LIGHT_LEVEL": SensorEntityDescription(
        key="V_LEVEL_S_LIGHT_LEVEL",
        native_unit_of_measurement=LIGHT_LUX,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_LEVEL_S_MOISTURE": SensorEntityDescription(
        key="V_LEVEL_S_MOISTURE",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
    ),
    "V_VOLTAGE": SensorEntityDescription(
        key="V_VOLTAGE",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_CURRENT": SensorEntityDescription(
        key="V_CURRENT",
        native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_PH": SensorEntityDescription(
        key="V_PH",
        native_unit_of_measurement="pH",
    ),
    "V_ORP": SensorEntityDescription(
        key="V_ORP",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_MILLIVOLT,
    ),
    "V_EC": SensorEntityDescription(
        key="V_EC",
        native_unit_of_measurement=CONDUCTIVITY,
    ),
    "V_VAR": SensorEntityDescription(
        key="V_VAR",
        native_unit_of_measurement="var",
    ),
    "V_VA": SensorEntityDescription(
        key="V_VA",
        native_unit_of_measurement=POWER_VOLT_AMPERE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors sensor."""
        mysensors.setup_mysensors_platform(
            hass,
            Platform.SENSOR,
            discovery_info,
            MySensorsSensor,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.SENSOR),
            async_discover,
        ),
    )


class MySensorsSensor(mysensors.device.MySensorsEntity, SensorEntity):
    """Representation of a MySensors Sensor child node."""

    _attr_force_update = True

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Set up the instance."""
        super().__init__(*args, **kwargs)
        if entity_description := self._get_entity_description():
            self.entity_description = entity_description

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        return self._values.get(self.value_type)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement of this entity."""
        set_req = self.gateway.const.SetReq
        if (
            AwesomeVersion(self.gateway.protocol_version) >= AwesomeVersion("1.5")
            and set_req.V_UNIT_PREFIX in self._values
        ):
            custom_unit: str = self._values[set_req.V_UNIT_PREFIX]
            return custom_unit

        if set_req(self.value_type) == set_req.V_TEMP:
            if self.hass.config.units.is_metric:
                return TEMP_CELSIUS
            return TEMP_FAHRENHEIT

        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    def _get_entity_description(self) -> SensorEntityDescription | None:
        """Return the sensor entity description."""
        set_req = self.gateway.const.SetReq
        entity_description = SENSORS.get(set_req(self.value_type).name)

        if not entity_description:
            pres = self.gateway.const.Presentation
            entity_description = SENSORS.get(
                f"{set_req(self.value_type).name}_{pres(self.child_type).name}"
            )

        return entity_description
