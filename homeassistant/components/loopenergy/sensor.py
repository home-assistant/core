"""Support for Loop Energy sensors."""
import logging

import pyloopenergy
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    EVENT_HOMEASSISTANT_STOP,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_ELEC = "electricity"
CONF_GAS = "gas"

CONF_ELEC_SERIAL = "electricity_serial"
CONF_ELEC_SECRET = "electricity_secret"

CONF_GAS_SERIAL = "gas_serial"
CONF_GAS_SECRET = "gas_secret"
CONF_GAS_CALORIFIC = "gas_calorific"

CONF_GAS_TYPE = "gas_type"

DEFAULT_CALORIFIC = 39.11
DEFAULT_UNIT = "kW"

ELEC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ELEC_SERIAL): cv.string,
        vol.Required(CONF_ELEC_SECRET): cv.string,
    }
)

GAS_TYPE_SCHEMA = vol.In([CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL])

GAS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GAS_SERIAL): cv.string,
        vol.Required(CONF_GAS_SECRET): cv.string,
        vol.Optional(CONF_GAS_TYPE, default=CONF_UNIT_SYSTEM_METRIC): GAS_TYPE_SCHEMA,
        vol.Optional(CONF_GAS_CALORIFIC, default=DEFAULT_CALORIFIC): vol.Coerce(float),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_ELEC): ELEC_SCHEMA, vol.Optional(CONF_GAS): GAS_SCHEMA}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Loop Energy sensors."""
    elec_config = config.get(CONF_ELEC)
    gas_config = config.get(CONF_GAS, {})

    controller = pyloopenergy.LoopEnergy(
        elec_config.get(CONF_ELEC_SERIAL),
        elec_config.get(CONF_ELEC_SECRET),
        gas_config.get(CONF_GAS_SERIAL),
        gas_config.get(CONF_GAS_SECRET),
        gas_config.get(CONF_GAS_TYPE),
        gas_config.get(CONF_GAS_CALORIFIC),
    )

    def stop_loopenergy(event):
        """Shutdown loopenergy thread on exit."""
        _LOGGER.info("Shutting down loopenergy")
        controller.terminate()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_loopenergy)

    sensors = [LoopEnergyElec(controller)]

    if gas_config.get(CONF_GAS_SERIAL):
        sensors.append(LoopEnergyGas(controller))

    add_entities(sensors)


class LoopEnergySensor(SensorEntity):
    """Implementation of an Loop Energy base sensor."""

    def __init__(self, controller):
        """Initialize the sensor."""
        self._state = None
        self._unit_of_measurement = DEFAULT_UNIT
        self._controller = controller
        self._name = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def _callback(self):
        self.schedule_update_ha_state(True)


class LoopEnergyElec(LoopEnergySensor):
    """Implementation of an Loop Energy Electricity sensor."""

    def __init__(self, controller):
        """Initialize the sensor."""
        super().__init__(controller)
        self._name = "Power Usage"

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._controller.subscribe_elecricity(self._callback)

    def update(self):
        """Get the cached Loop energy reading."""
        self._state = round(self._controller.electricity_useage, 2)


class LoopEnergyGas(LoopEnergySensor):
    """Implementation of an Loop Energy Gas sensor."""

    def __init__(self, controller):
        """Initialize the sensor."""
        super().__init__(controller)
        self._name = "Gas Usage"

    async def async_added_to_hass(self):
        """Subscribe to updates."""
        self._controller.subscribe_gas(self._callback)

    def update(self):
        """Get the cached Loop gas reading."""
        self._state = round(self._controller.gas_useage, 2)
