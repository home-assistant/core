"""Support for OpenTherm Gateway binary sensors."""
import logging
from pprint import pformat

import pyotgw.vars as gw_vars

from homeassistant.components.binary_sensor import (
    ENTITY_ID_FORMAT,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .const import (
    DATA_GATEWAYS,
    DATA_OPENTHERM_GW,
    DEPRECATED_BINARY_SENSOR_SOURCE_LOOKUP,
    TRANSLATE_SOURCE,
)

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_INFO: dict[str, list] = {
    # [device_class, friendly_name format, [status source, ...]]
    gw_vars.DATA_MASTER_CH_ENABLED: [
        None,
        "Thermostat Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_DHW_ENABLED: [
        None,
        "Thermostat Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_COOLING_ENABLED: [
        None,
        "Thermostat Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_OTC_ENABLED: [
        None,
        "Thermostat Outside Temperature Correction {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_MASTER_CH2_ENABLED: [
        None,
        "Thermostat Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_FAULT_IND: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Central Heating {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Hot Water {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_FLAME_ON: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Flame {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_COOLING_ACTIVE: [
        BinarySensorDeviceClass.COLD,
        "Boiler Cooling {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH2_ACTIVE: [
        BinarySensorDeviceClass.HEAT,
        "Boiler Central Heating 2 {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DIAG_IND: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Diagnostics {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_PRESENT: [
        None,
        "Boiler Hot Water Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CONTROL_TYPE: [
        None,
        "Boiler Control Type {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_COOLING_SUPPORTED: [
        None,
        "Boiler Cooling Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_DHW_CONFIG: [
        None,
        "Boiler Hot Water Configuration {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_MASTER_LOW_OFF_PUMP: [
        None,
        "Boiler Pump Commands Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_CH2_PRESENT: [
        None,
        "Boiler Central Heating 2 Present {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_SERVICE_REQ: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Service Required {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_REMOTE_RESET: [
        None,
        "Boiler Remote Reset Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_LOW_WATER_PRESS: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Low Water Pressure {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_GAS_FAULT: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Gas Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_AIR_PRESS_FAULT: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Air Pressure Fault {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_SLAVE_WATER_OVERTEMP: [
        BinarySensorDeviceClass.PROBLEM,
        "Boiler Water Overtemperature {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_TRANSFER_DHW: [
        None,
        "Remote Hot Water Setpoint Transfer Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_TRANSFER_MAX_CH: [
        None,
        "Remote Maximum Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_RW_DHW: [
        None,
        "Remote Hot Water Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_REMOTE_RW_MAX_CH: [
        None,
        "Remote Central Heating Setpoint Write Support {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROVRD_MAN_PRIO: [
        None,
        "Remote Override Manual Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.DATA_ROVRD_AUTO_PRIO: [
        None,
        "Remote Override Program Change Priority {}",
        [gw_vars.BOILER, gw_vars.THERMOSTAT],
    ],
    gw_vars.OTGW_GPIO_A_STATE: [None, "Gateway GPIO A {}", [gw_vars.OTGW]],
    gw_vars.OTGW_GPIO_B_STATE: [None, "Gateway GPIO B {}", [gw_vars.OTGW]],
    gw_vars.OTGW_IGNORE_TRANSITIONS: [
        None,
        "Gateway Ignore Transitions {}",
        [gw_vars.OTGW],
    ],
    gw_vars.OTGW_OVRD_HB: [None, "Gateway Override High Byte {}", [gw_vars.OTGW]],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the OpenTherm Gateway binary sensors."""
    sensors = []
    deprecated_sensors = []
    gw_dev = hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]]
    ent_reg = er.async_get(hass)
    for var, info in BINARY_SENSOR_INFO.items():
        device_class = info[0]
        friendly_name_format = info[1]
        status_sources = info[2]

        for source in status_sources:
            sensors.append(
                OpenThermBinarySensor(
                    gw_dev,
                    var,
                    source,
                    device_class,
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
                    DeprecatedOpenThermBinarySensor(
                        gw_dev,
                        var,
                        device_class,
                        friendly_name_format,
                    )
                )

    sensors.extend(deprecated_sensors)

    if deprecated_sensors:
        _LOGGER.warning(
            "The following binary_sensor entities are deprecated and may "
            "no longer behave as expected. They will be removed in a "
            "future version. You can force removal of these entities by "
            "disabling them and restarting Home Assistant.\n%s",
            pformat([s.entity_id for s in deprecated_sensors]),
        )

    async_add_entities(sensors)


class OpenThermBinarySensor(BinarySensorEntity):
    """Represent an OpenTherm Gateway binary sensor."""

    _attr_should_poll = False

    def __init__(self, gw_dev, var, source, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{source}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = source
        self._state = None
        self._device_class = device_class
        if TRANSLATE_SOURCE[source] is not None:
            friendly_name_format = (
                f"{friendly_name_format} ({TRANSLATE_SOURCE[source]})"
            )
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates from the component."""
        _LOGGER.debug("Added OpenTherm Gateway binary sensor %s", self._friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from updates from the component."""
        _LOGGER.debug(
            "Removing OpenTherm Gateway binary sensor %s", self._friendly_name
        )
        self._unsub_updates()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._state is not None

    @property
    def entity_registry_enabled_default(self):
        """Disable binary_sensors by default."""
        return False

    @callback
    def receive_report(self, status):
        """Handle status updates from the component."""
        state = status[self._source].get(self._var)
        self._state = None if state is None else bool(state)
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the friendly name."""
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
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the class of this device."""
        return self._device_class


class DeprecatedOpenThermBinarySensor(OpenThermBinarySensor):
    """Represent a deprecated OpenTherm Gateway Binary Sensor."""

    # pylint: disable=super-init-not-called
    def __init__(self, gw_dev, var, device_class, friendly_name_format):
        """Initialize the binary sensor."""
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, f"{var}_{gw_dev.gw_id}", hass=gw_dev.hass
        )
        self._gateway = gw_dev
        self._var = var
        self._source = DEPRECATED_BINARY_SENSOR_SOURCE_LOOKUP[var]
        self._state = None
        self._device_class = device_class
        self._friendly_name = friendly_name_format.format(gw_dev.name)
        self._unsub_updates = None

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._gateway.gw_id}-{self._var}"
