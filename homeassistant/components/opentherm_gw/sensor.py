"""Support for OpenTherm Gateway sensors."""

from dataclasses import dataclass

import pyotgw.vars as gw_vars

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import OpenThermGatewayHub
from .const import DATA_GATEWAYS, DATA_OPENTHERM_GW
from .entity import (
    OpenThermBaseEntity,
    OpenThermBoilerDeviceEntity,
    OpenThermEntityDescription,
    OpenThermGatewayDeviceEntity,
    OpenThermThermostatDeviceEntity,
)

SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION = 1


@dataclass(frozen=True, kw_only=True)
class OpenThermSensorEntityDescription(
    SensorEntityDescription, OpenThermEntityDescription
):
    """Describes an opentherm_gw sensor entity."""

    make_state_lowercase: bool = True


BOILER_SENSOR_DESCRIPTIONS: tuple[OpenThermSensorEntityDescription, ...] = (
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CONTROL_SETPOINT,
        translation_key="control_setpoint_n",
        translation_placeholders={"circuit_number": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_MEMBERID,
        translation_key="manufacturer_id",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_OEM_FAULT,
        translation_key="oem_fault_code",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_COOLING_CONTROL,
        translation_key="cooling_control",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CONTROL_SETPOINT_2,
        translation_key="control_setpoint_n",
        translation_placeholders={"circuit_number": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD,
        translation_key="max_relative_mod_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_MAX_CAPACITY,
        translation_key="max_capacity",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_MIN_MOD_LEVEL,
        translation_key="min_mod_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_REL_MOD_LEVEL,
        translation_key="relative_mod_level",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CH_WATER_PRESS,
        translation_key="central_heating_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_FLOW_RATE,
        translation_key="hot_water_flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CH_WATER_TEMP,
        translation_key="central_heating_temperature_n",
        translation_placeholders={"circuit_number": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_TEMP,
        translation_key="hot_water_temperature_n",
        translation_placeholders={"circuit_number": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_RETURN_WATER_TEMP,
        translation_key="return_water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SOLAR_STORAGE_TEMP,
        translation_key="solar_storage_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SOLAR_COLL_TEMP,
        translation_key="solar_collector_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CH_WATER_TEMP_2,
        translation_key="central_heating_temperature_n",
        translation_placeholders={"circuit_number": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_TEMP_2,
        translation_key="hot_water_temperature_n",
        translation_placeholders={"circuit_number": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_EXHAUST_TEMP,
        translation_key="exhaust_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DHW_MAX_SETP,
        translation_key="max_hot_water_setpoint_upper",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_DHW_MIN_SETP,
        translation_key="max_hot_water_setpoint_lower",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CH_MAX_SETP,
        translation_key="max_central_heating_setpoint_upper",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_CH_MIN_SETP,
        translation_key="max_central_heating_setpoint_lower",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_SETPOINT,
        translation_key="hot_water_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_MAX_CH_SETPOINT,
        translation_key="max_central_heating_setpoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_OEM_DIAG,
        translation_key="oem_diagnostic_code",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_TOTAL_BURNER_STARTS,
        translation_key="total_burner_starts",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="starts",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CH_PUMP_STARTS,
        translation_key="central_heating_pump_starts",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="starts",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_PUMP_STARTS,
        translation_key="hot_water_pump_starts",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="starts",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_BURNER_STARTS,
        translation_key="hot_water_burner_starts",
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="starts",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_TOTAL_BURNER_HOURS,
        translation_key="total_burner_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_CH_PUMP_HOURS,
        translation_key="central_heating_pump_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_PUMP_HOURS,
        translation_key="hot_water_pump_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_DHW_BURNER_HOURS,
        translation_key="hot_water_burner_hours",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfTime.HOURS,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_OT_VERSION,
        translation_key="opentherm_version",
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_PRODUCT_TYPE,
        translation_key="product_type",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_SLAVE_PRODUCT_VERSION,
        translation_key="product_version",
    ),
)

GATEWAY_SENSOR_DESCRIPTIONS: tuple[OpenThermSensorEntityDescription, ...] = (
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_MODE,
        translation_key="operating_mode",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_DHW_OVRD,
        translation_key="hot_water_override_mode",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_ABOUT,
        translation_key="firmware_version",
        make_state_lowercase=False,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_BUILD,
        translation_key="firmware_build",
        make_state_lowercase=False,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_CLOCKMHZ,
        translation_key="clock_speed",
        make_state_lowercase=False,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_A,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "A"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_B,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "B"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_C,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "C"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_D,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "D"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_E,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "E"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_LED_F,
        translation_key="led_mode_n",
        translation_placeholders={"led_id": "F"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_GPIO_A,
        translation_key="gpio_mode_n",
        translation_placeholders={"gpio_id": "A"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_GPIO_B,
        translation_key="gpio_mode_n",
        translation_placeholders={"gpio_id": "B"},
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_SB_TEMP,
        translation_key="setback_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_SETP_OVRD_MODE,
        translation_key="room_setpoint_override_mode",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_SMART_PWR,
        translation_key="smart_power_mode",
        make_state_lowercase=False,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_THRM_DETECT,
        translation_key="thermostat_detection_mode",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.OTGW_VREF,
        translation_key="reference_voltage",
    ),
)

THERMOSTAT_SENSOR_DESCRIPTIONS: tuple[OpenThermSensorEntityDescription, ...] = (
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_MASTER_MEMBERID,
        translation_key="manufacturer_id",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_ROOM_SETPOINT_OVRD,
        translation_key="room_setpoint_override",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_ROOM_SETPOINT,
        translation_key="room_setpoint_n",
        translation_placeholders={"setpoint_id": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_ROOM_SETPOINT_2,
        translation_key="room_setpoint_n",
        translation_placeholders={"setpoint_id": "2"},
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_ROOM_TEMP,
        translation_key="room_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_OUTSIDE_TEMP,
        translation_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_MASTER_OT_VERSION,
        translation_key="opentherm_version",
        suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_MASTER_PRODUCT_TYPE,
        translation_key="product_type",
    ),
    OpenThermSensorEntityDescription(
        key=gw_vars.DATA_MASTER_PRODUCT_VERSION,
        translation_key="product_version",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway sensors."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    for klass, descriptions in (
        (OpenThermBoilerSensorEntity, BOILER_SENSOR_DESCRIPTIONS),
        (OpenThermGatewaySensorEntity, GATEWAY_SENSOR_DESCRIPTIONS),
        (OpenThermThermostatSensorEntity, THERMOSTAT_SENSOR_DESCRIPTIONS),
    ):
        async_add_entities(
            klass(
                gw_hub,
                description,
            )
            for description in descriptions
        )


class OpenThermSensor(OpenThermBaseEntity, SensorEntity):
    """Representation of an OpenTherm sensor."""

    entity_description: OpenThermSensorEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        description: OpenThermSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(gw_hub, description)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{description.key}_{self._data_source}_{gw_hub.hub_id}",
            hass=gw_hub.hass,
        )

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        self._attr_available = self._gateway.connected
        value = status[self._data_source].get(self.entity_description.key)
        if isinstance(value, str) and self.entity_description.make_state_lowercase:
            value = value.lower()
        self._attr_native_value = value
        self.async_write_ha_state()


class OpenThermBoilerSensorEntity(OpenThermSensor, OpenThermBoilerDeviceEntity):
    """Represent an OpenTherm sensor on the Boiler."""

    entity_description: OpenThermSensorEntityDescription


class OpenThermGatewaySensorEntity(OpenThermSensor, OpenThermGatewayDeviceEntity):
    """Represent an OpenTherm sensor on the Gateway."""

    entity_description: OpenThermSensorEntityDescription


class OpenThermThermostatSensorEntity(OpenThermSensor, OpenThermThermostatDeviceEntity):
    """Represent an OpenTherm sensor on the Thermostat."""

    entity_description: OpenThermSensorEntityDescription
