"""Support for OpenTherm Gateway sensors."""
import logging
from pprint import pformat

import pyotgw.vars as gw_vars

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ID,
    PERCENTAGE,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import (
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DEPRECATED_SENSOR_SOURCE_LOOKUP,
    TRANSLATE_SOURCE,
)

_LOGGER = logging.getLogger(__name__)
SENSOR_INFO: dict[str, list] = {
    # [device_class, unit, friendly_name, [status source, ...]]
    gw_vars.DATA_CONTROL_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Control Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_MEMBERID: [
        None,
        None,
        "Thermostat Member ID {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MEMBERID: [
        None,
        None,
        "Boiler Member ID {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_OEM_FAULT: [
        None,
        None,
        "Boiler OEM Fault Code {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_COOLING_CONTROL: [
        None,
        PERCENTAGE,
        "Cooling Control Signal {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CONTROL_SETPOINT_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Control Setpoint 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT_OVRD: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint Override {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MAX_RELATIVE_MOD: [
        None,
        PERCENTAGE,
        "Boiler Maximum Relative Modulation {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MAX_CAPACITY: [
        None,
        UnitOfPower.KILO_WATT,
        "Boiler Maximum Capacity {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MIN_MOD_LEVEL: [
        None,
        PERCENTAGE,
        "Boiler Minimum Modulation Level {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REL_MOD_LEVEL: [
        None,
        PERCENTAGE,
        "Relative Modulation Level {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_PRESS: [
        None,
        UnitOfPressure.BAR,
        "Central Heating Water Pressure {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_FLOW_RATE: [
        None,
        f"{UnitOfVolume.LITERS}/{UnitOfTime.MINUTES}",
        "Hot Water Flow Rate {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_SETPOINT_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Setpoint 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROOM_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Room Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Central Heating Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_OUTSIDE_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Outside Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_RETURN_WATER_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Return Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SOLAR_STORAGE_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Solar Storage Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SOLAR_COLL_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Solar Collector Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_WATER_TEMP_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Central Heating 2 Water Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_TEMP_2: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water 2 Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_EXHAUST_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Exhaust Temperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_MAX_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Maximum Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_MIN_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Minimum Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_MAX_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Boiler Maximum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_MIN_SETP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Boiler Minimum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Hot Water Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MAX_CH_SETPOINT: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Maximum Central Heating Setpoint {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_OEM_DIAG: [
        None,
        None,
        "OEM Diagnostic Code {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_TOTAL_BURNER_STARTS: [
        None,
        None,
        "Total Burner Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_PUMP_STARTS: [
        None,
        None,
        "Central Heating Pump Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_PUMP_STARTS: [
        None,
        None,
        "Hot Water Pump Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_BURNER_STARTS: [
        None,
        None,
        "Hot Water Burner Starts {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_TOTAL_BURNER_HOURS: [
        None,
        UnitOfTime.HOURS,
        "Total Burner Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_CH_PUMP_HOURS: [
        None,
        UnitOfTime.HOURS,
        "Central Heating Pump Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_PUMP_HOURS: [
        None,
        UnitOfTime.HOURS,
        "Hot Water Pump Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_DHW_BURNER_HOURS: [
        None,
        UnitOfTime.HOURS,
        "Hot Water Burner Hours {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_OT_VERSION: [
        None,
        None,
        "Thermostat OpenTherm Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_OT_VERSION: [
        None,
        None,
        "Boiler OpenTherm Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_PRODUCT_TYPE: [
        None,
        None,
        "Thermostat Product Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_PRODUCT_VERSION: [
        None,
        None,
        "Thermostat Product Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_PRODUCT_TYPE: [
        None,
        None,
        "Boiler Product Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_PRODUCT_VERSION: [
        None,
        None,
        "Boiler Product Version {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.OTGW_MODE: [None, None, "Gateway/Monitor Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_DHW_OVRD: [
        None,
        None,
        "Gateway Hot Water Override Mode {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_ABOUT: [None, None, "Gateway Firmware Version {}", [gw_vars.OTGW]],
    gw_vars.OTGW_BUILD: [None, None, "Gateway Firmware Build {}", [gw_vars.OTGW]],
    gw_vars.OTGW_CLOCKMHZ: [None, None, "Gateway Clock Speed {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_A: [None, None, "Gateway LED A Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_B: [None, None, "Gateway LED B Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_C: [None, None, "Gateway LED C Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_D: [None, None, "Gateway LED D Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_E: [None, None, "Gateway LED E Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_LED_F: [None, None, "Gateway LED F Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_GPIO_A: [None, None, "Gateway GPIO A Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_GPIO_B: [None, None, "Gateway GPIO B Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_SB_TEMP: [
        SensorDeviceClass.TEMPERATURE,
        UnitOfTemperature.CELSIUS,
        "Gateway Setback Temperature {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_SETP_OVRD_MODE: [
        None,
        None,
        "Gateway Room Setpoint Override Mode {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_SMART_PWR: [None, None, "Gateway Smart Power Mode {}", [gw_vars.OTGW]],
    gw_vars.OTGW_THRM_DETECT: [
        None,
        None,
        "Gateway Thermostat Detection {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_VREF: [
        None,
        None,
        "Gateway Reference Voltage Setting {}",
        [gw_vars.OTGW],
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway sensors."""
    sensors = []
    deprecated_sensors = []
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]
    ent_reg = er.async_get(hass)
    for var, info in SENSOR_INFO.items():
        device_class = info[0]
        unit = info[1]
        friendly_name_format = info[2]
        status_sources = info[3]

        for source in status_sources:
            sensors.append(
                OpenThermSensor(
                    gw_dev,
                    var,
                    source,
                    device_class,
                    unit,
                    friendly_name_format,
                )
            )

        old_style_entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        old_ent = ent_reg.async_get(old_style_entity_id)
        if old_ent and old_ent.config_entry_id == config_entry.entry_id:
            if old_ent.disabled:
                ent_reg.async_remove(old_style_entity_id)
            else:
                deprecated_sensors.append(
                    DeprecatedOpenThermSensor(
                        gw_dev,
                        var,
                        device_class,
                        unit,
                        friendly_name_format,
                    )
                )

    sensors.extend(deprecated_sensors)

    if deprecated_sensors:
        _LOGGER.warning(
            "The following sensor entities are deprecated and may no "
            "longer behave as expected. They will be removed in a future "
            "version. You can force removal of these entities by disabling "
            "them and restarting Home Assistant.\n%s",
            pformat([s.entity_id for s in deprecated_sensors]),
        )

    async_add_entities(sensors)


class OpenThermSensor(SensorEntity):
    """Representation of an OpenTherm Gateway sensor."""

    _attr_should_poll = False

    def __init__(self, gw_dev, var, source, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{source}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = source
        self._value = None
        self._device_class = device_class
        self._unit = unit
        if TRANSLATE_SOURCE[source] is not None:
            friendly_name_format = (
                f"{friendly_name_format} ({TRANSLATE_SOURCE[source]})"
            )
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway sensor %s", self._friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway sensor %s", self._friendly_name)
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._value is not None

    @property
    def entity_registry_enabled_default(self):
        """Disable sensors by default."""
        return False

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        value = status[self._source].get(self._var)
        if isinstance(value, float):
            value = f"{value:2.1f}"
        self._value = value
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the friendly name of the sensor."""
        return self._friendly_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._gateway.gw_id)},
            manufacturer="Schelte Bron",
            model="OpenTherm Gateway",
            name=self._gateway.name,
            sw_version=self._gateway.gw_version,
        )

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._gateway.gw_id}-{self._source}-{self._var}"

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit


class DeprecatedOpenThermSensor(OpenThermSensor):
    """Represent a deprecated OpenTherm Gateway Sensor."""

    # pylint: disable=super-init-not-called
    def __init__(self, gw_dev, var, device_class, unit, friendly_name_format):
        """Initialize the OpenTherm Gateway sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = DEPRECATED_SENSOR_SOURCE_LOOKUP[var]
        self._value = None
        self._device_class = device_class
        self._unit = unit
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._gateway.gw_id}-{self._var}"
