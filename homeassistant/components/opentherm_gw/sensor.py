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
from .entity import OpenThermEntity, OpenThermEntityDescription

SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION = 1


@dataclass(frozen=True, kw_only=True)
class OpenThermSensorEntityDescription(
    SensorEntityDescription, OpenThermEntityDescription
):
    """Describes opentherm_gw sensor entity."""


SENSOR_INFO: tuple[tuple[list[str], OpenThermSensorEntityDescription], ...] = (
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CONTROL_SETPOINT,
            friendly_name_format="Control Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_MASTER_MEMBERID,
            friendly_name_format="Thermostat Member ID {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_MEMBERID,
            friendly_name_format="Boiler Member ID {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_OEM_FAULT,
            friendly_name_format="Boiler OEM Fault Code {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_COOLING_CONTROL,
            friendly_name_format="Cooling Control Signal {}",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CONTROL_SETPOINT_2,
            friendly_name_format="Control Setpoint 2 {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_ROOM_SETPOINT_OVRD,
            friendly_name_format="Room Setpoint Override {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD,
            friendly_name_format="Boiler Maximum Relative Modulation {}",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_MAX_CAPACITY,
            friendly_name_format="Boiler Maximum Capacity {}",
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.POWER,
            native_unit_of_measurement=UnitOfPower.KILO_WATT,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_MIN_MOD_LEVEL,
            friendly_name_format="Boiler Minimum Modulation Level {}",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_ROOM_SETPOINT,
            friendly_name_format="Room Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_REL_MOD_LEVEL,
            friendly_name_format="Relative Modulation Level {}",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CH_WATER_PRESS,
            friendly_name_format="Central Heating Water Pressure {}",
            device_class=SensorDeviceClass.PRESSURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPressure.BAR,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_FLOW_RATE,
            friendly_name_format="Hot Water Flow Rate {}",
            device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_ROOM_SETPOINT_2,
            friendly_name_format="Room Setpoint 2 {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_ROOM_TEMP,
            friendly_name_format="Room Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CH_WATER_TEMP,
            friendly_name_format="Central Heating Water Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_TEMP,
            friendly_name_format="Hot Water Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_OUTSIDE_TEMP,
            friendly_name_format="Outside Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_RETURN_WATER_TEMP,
            friendly_name_format="Return Water Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SOLAR_STORAGE_TEMP,
            friendly_name_format="Solar Storage Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SOLAR_COLL_TEMP,
            friendly_name_format="Solar Collector Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CH_WATER_TEMP_2,
            friendly_name_format="Central Heating 2 Water Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_TEMP_2,
            friendly_name_format="Hot Water 2 Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_EXHAUST_TEMP,
            friendly_name_format="Exhaust Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DHW_MAX_SETP,
            friendly_name_format="Hot Water Maximum Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_DHW_MIN_SETP,
            friendly_name_format="Hot Water Minimum Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CH_MAX_SETP,
            friendly_name_format="Boiler Maximum Central Heating Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_CH_MIN_SETP,
            friendly_name_format="Boiler Minimum Central Heating Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_SETPOINT,
            friendly_name_format="Hot Water Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_MAX_CH_SETPOINT,
            friendly_name_format="Maximum Central Heating Setpoint {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_OEM_DIAG,
            friendly_name_format="OEM Diagnostic Code {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_TOTAL_BURNER_STARTS,
            friendly_name_format="Total Burner Starts {}",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="starts",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CH_PUMP_STARTS,
            friendly_name_format="Central Heating Pump Starts {}",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="starts",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_PUMP_STARTS,
            friendly_name_format="Hot Water Pump Starts {}",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="starts",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_BURNER_STARTS,
            friendly_name_format="Hot Water Burner Starts {}",
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="starts",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_TOTAL_BURNER_HOURS,
            friendly_name_format="Total Burner Hours {}",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfTime.HOURS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_CH_PUMP_HOURS,
            friendly_name_format="Central Heating Pump Hours {}",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfTime.HOURS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_PUMP_HOURS,
            friendly_name_format="Hot Water Pump Hours {}",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfTime.HOURS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_DHW_BURNER_HOURS,
            friendly_name_format="Hot Water Burner Hours {}",
            device_class=SensorDeviceClass.DURATION,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfTime.HOURS,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_MASTER_OT_VERSION,
            friendly_name_format="Thermostat OpenTherm Version {}",
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_OT_VERSION,
            friendly_name_format="Boiler OpenTherm Version {}",
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_MASTER_PRODUCT_TYPE,
            friendly_name_format="Thermostat Product Type {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_MASTER_PRODUCT_VERSION,
            friendly_name_format="Thermostat Product Version {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_PRODUCT_TYPE,
            friendly_name_format="Boiler Product Type {}",
        ),
    ),
    (
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
        OpenThermSensorEntityDescription(
            key=gw_vars.DATA_SLAVE_PRODUCT_VERSION,
            friendly_name_format="Boiler Product Version {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_MODE,
            friendly_name_format="Gateway/Monitor Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_DHW_OVRD,
            friendly_name_format="Gateway Hot Water Override Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_ABOUT,
            friendly_name_format="Gateway Firmware Version {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_BUILD,
            friendly_name_format="Gateway Firmware Build {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_CLOCKMHZ,
            friendly_name_format="Gateway Clock Speed {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_A,
            friendly_name_format="Gateway LED A Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_B,
            friendly_name_format="Gateway LED B Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_C,
            friendly_name_format="Gateway LED C Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_D,
            friendly_name_format="Gateway LED D Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_E,
            friendly_name_format="Gateway LED E Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_LED_F,
            friendly_name_format="Gateway LED F Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_GPIO_A,
            friendly_name_format="Gateway GPIO A Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_GPIO_B,
            friendly_name_format="Gateway GPIO B Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_SB_TEMP,
            friendly_name_format="Gateway Setback Temperature {}",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            suggested_display_precision=SENSOR_FLOAT_SUGGESTED_DISPLAY_PRECISION,
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_SETP_OVRD_MODE,
            friendly_name_format="Gateway Room Setpoint Override Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_SMART_PWR,
            friendly_name_format="Gateway Smart Power Mode {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_THRM_DETECT,
            friendly_name_format="Gateway Thermostat Detection {}",
        ),
    ),
    (
        [gw_vars.OTGW],
        OpenThermSensorEntityDescription(
            key=gw_vars.OTGW_VREF,
            friendly_name_format="Gateway Reference Voltage Setting {}",
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway sensors."""
    gw_hub = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]

    async_add_entities(
        OpenThermSensor(
            gw_hub,
            source,
            description,
        )
        for sources, description in SENSOR_INFO
        for source in sources
    )


class OpenThermSensor(OpenThermEntity, SensorEntity):
    """Representation of an OpenTherm Gateway sensor."""

    entity_description: OpenThermSensorEntityDescription

    def __init__(
        self,
        gw_hub: OpenThermGatewayHub,
        source: str,
        description: OpenThermSensorEntityDescription,
    ) -> None:
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT,
            f"{description.key}_{source}_{gw_hub.hub_id}",
            hass=gw_hub.hass,
        )
        super().__init__(gw_hub, source, description)

    @callback
    def receive_report(self, status: dict[str, dict]) -> None:
        """Handle status updates from the component."""
        self._attr_available = self._gateway.connected
        value = status[self._source].get(self.entity_description.key)
        self._attr_native_value = value
        self.async_write_ha_state()
