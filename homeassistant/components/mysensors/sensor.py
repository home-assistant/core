"""Support for MySensors sensors."""

from __future__ import annotations

from typing import Any

from awesomeversion import AwesomeVersion
from mysensors import BaseAsyncGateway

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfApparentPower,
    UnitOfConductivity,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfReactivePower,
    UnitOfSoundPressure,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.unit_system import METRIC_SYSTEM

from . import setup_mysensors_platform
from .const import (
    ATTR_GATEWAY_ID,
    ATTR_NODE_ID,
    DOMAIN,
    MYSENSORS_DISCOVERY,
    MYSENSORS_GATEWAYS,
    MYSENSORS_NODE_DISCOVERY,
    DiscoveryInfo,
    NodeDiscoveryInfo,
)
from .entity import MySensorNodeEntity, MySensorsChildEntity

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
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    "V_WEIGHT": SensorEntityDescription(
        key="V_WEIGHT",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
    ),
    "V_DISTANCE": SensorEntityDescription(
        key="V_DISTANCE",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
    ),
    "V_IMPEDANCE": SensorEntityDescription(
        key="V_IMPEDANCE",
        native_unit_of_measurement="ohm",
    ),
    "V_WATT": SensorEntityDescription(
        key="V_WATT",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_KWH": SensorEntityDescription(
        key="V_KWH",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "V_LIGHT_LEVEL": SensorEntityDescription(
        key="V_LIGHT_LEVEL",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:white-balance-sunny",
    ),
    "V_FLOW": SensorEntityDescription(
        # The documentation on this measurement is inconsistent.
        # Better not to set a device class here yet.
        key="V_FLOW",
        native_unit_of_measurement=UnitOfLength.METERS,
        icon="mdi:gauge",
    ),
    "V_VOLUME": SensorEntityDescription(
        key="V_VOLUME",
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.VOLUME,
    ),
    "V_LEVEL_S_SOUND": SensorEntityDescription(
        key="V_LEVEL_S_SOUND",
        native_unit_of_measurement=UnitOfSoundPressure.DECIBEL,
        device_class=SensorDeviceClass.SOUND_PRESSURE,
    ),
    "V_LEVEL_S_VIBRATION": SensorEntityDescription(
        key="V_LEVEL_S_VIBRATION",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
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
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_CURRENT": SensorEntityDescription(
        key="V_CURRENT",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "V_IR_RECORD": SensorEntityDescription(
        key="V_IR_RECORD",
        icon="mdi:remote",
    ),
    "V_PH": SensorEntityDescription(
        key="V_PH",
        native_unit_of_measurement="pH",
    ),
    "V_ORP": SensorEntityDescription(
        key="V_ORP",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "V_EC": SensorEntityDescription(
        key="V_EC",
        native_unit_of_measurement=UnitOfConductivity.MICROSIEMENS_PER_CM,
    ),
    "V_VAR": SensorEntityDescription(
        key="V_VAR",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
    ),
    "V_VA": SensorEntityDescription(
        key="V_VA",
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        device_class=SensorDeviceClass.APPARENT_POWER,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    async def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors sensor."""
        setup_mysensors_platform(
            hass,
            Platform.SENSOR,
            discovery_info,
            MySensorsSensor,
            async_add_entities=async_add_entities,
        )

    @callback
    def async_node_discover(discovery_info: NodeDiscoveryInfo) -> None:
        """Add battery sensor for each MySensors node."""
        gateway_id = discovery_info[ATTR_GATEWAY_ID]
        node_id = discovery_info[ATTR_NODE_ID]
        gateway: BaseAsyncGateway = hass.data[DOMAIN][MYSENSORS_GATEWAYS][gateway_id]
        async_add_entities([MyBatterySensor(gateway_id, gateway, node_id)])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.SENSOR),
            async_discover,
        ),
    )

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            MYSENSORS_NODE_DISCOVERY,
            async_node_discover,
        ),
    )


class MyBatterySensor(MySensorNodeEntity, SensorEntity):
    """Battery sensor of MySensors node."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_force_update = True

    @property
    def unique_id(self) -> str:
        """Return a unique ID for use in home assistant."""
        return f"{self.gateway_id}-{self.node_id}-battery"

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return f"{self.node_name} Battery"

    @callback
    def _async_update_callback(self) -> None:
        """Update the controller with the latest battery level."""
        self._attr_native_value = self._node.battery_level
        self.async_write_ha_state()


class MySensorsSensor(MySensorsChildEntity, SensorEntity):
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
            if self.hass.config.units is METRIC_SYSTEM:
                return UnitOfTemperature.CELSIUS
            return UnitOfTemperature.FAHRENHEIT

        if hasattr(self, "entity_description"):
            return self.entity_description.native_unit_of_measurement
        return None

    def _get_entity_description(self) -> SensorEntityDescription | None:
        """Return the sensor entity description."""
        set_req = self.gateway.const.SetReq
        entity_description = SENSORS.get(set_req(self.value_type).name)

        if not entity_description:
            presentation = self.gateway.const.Presentation
            entity_description = SENSORS.get(
                f"{set_req(self.value_type).name}_{presentation(self.child_type).name}"
            )

        return entity_description
