"""Support for OpenTherm Gateway climate devices."""
import logging

from pyotgw import vars as gw_vars

from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateEntity
from homeassistant.components.climate.const import (
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ID,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import async_generate_entity_id

from . import DOMAIN
from .const import CONF_FLOOR_TEMP, CONF_PRECISION, DATA_GATEWAYS, DATA_OPENTHERM_GW

_LOGGER = logging.getLogger(__name__)

DEFAULT_FLOOR_TEMP = False

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up an OpenTherm Gateway climate entity."""
    ents = []
    ents.append(
        OpenThermClimate(
            hass.data[DATA_OPENTHERM_GW][DATA_GATEWAYS][config_entry.data[CONF_ID]],
            config_entry.options,
        )
    )

    async_add_entities(ents)


class OpenThermClimate(ClimateEntity):
    """Representation of a climate device."""

    def __init__(self, gw_dev, options):
        """Initialize the device."""
        self._gateway = gw_dev
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, gw_dev.gw_id, hass=gw_dev.hass
        )
        self.friendly_name = gw_dev.name
        self.floor_temp = options.get(CONF_FLOOR_TEMP, DEFAULT_FLOOR_TEMP)
        self.temp_precision = options.get(CONF_PRECISION)
        self._available = False
        self._current_operation = None
        self._current_temperature = None
        self._hvac_mode = HVAC_MODE_HEAT
        self._new_target_temperature = None
        self._target_temperature = None
        self._away_mode_a = None
        self._away_mode_b = None
        self._away_state_a = False
        self._away_state_b = False
        self._unsub_options = None
        self._unsub_updates = None

    @callback
    def update_options(self, entry):
        """Update climate entity options."""
        self.floor_temp = entry.options[CONF_FLOOR_TEMP]
        self.temp_precision = entry.options[CONF_PRECISION]
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Connect to the OpenTherm Gateway device."""
        _LOGGER.debug("Added OpenTherm Gateway climate device %s", self.friendly_name)
        self._unsub_updates = async_dispatcher_connect(
            self.hass, self._gateway.update_signal, self.receive_report
        )
        self._unsub_options = async_dispatcher_connect(
            self.hass, self._gateway.options_update_signal, self.update_options
        )

    async def async_will_remove_from_hass(self):
        """Unsubscribe from updates from the component."""
        _LOGGER.debug("Removing OpenTherm Gateway climate %s", self.friendly_name)
        self._unsub_options()
        self._unsub_updates()

    @callback
    def receive_report(self, status):
        """Receive and handle a new report from the Gateway."""
        self._available = bool(status)
        ch_active = status.get(gw_vars.DATA_SLAVE_CH_ACTIVE)
        flame_on = status.get(gw_vars.DATA_SLAVE_FLAME_ON)
        cooling_active = status.get(gw_vars.DATA_SLAVE_COOLING_ACTIVE)
        if ch_active and flame_on:
            self._current_operation = CURRENT_HVAC_HEAT
            self._hvac_mode = HVAC_MODE_HEAT
        elif cooling_active:
            self._current_operation = CURRENT_HVAC_COOL
            self._hvac_mode = HVAC_MODE_COOL
        else:
            self._current_operation = CURRENT_HVAC_IDLE

        self._current_temperature = status.get(gw_vars.DATA_ROOM_TEMP)
        temp_upd = status.get(gw_vars.DATA_ROOM_SETPOINT)

        if self._target_temperature != temp_upd:
            self._new_target_temperature = None
        self._target_temperature = temp_upd

        # GPIO mode 5: 0 == Away
        # GPIO mode 6: 1 == Away
        gpio_a_state = status.get(gw_vars.OTGW_GPIO_A)
        if gpio_a_state == 5:
            self._away_mode_a = 0
        elif gpio_a_state == 6:
            self._away_mode_a = 1
        else:
            self._away_mode_a = None
        gpio_b_state = status.get(gw_vars.OTGW_GPIO_B)
        if gpio_b_state == 5:
            self._away_mode_b = 0
        elif gpio_b_state == 6:
            self._away_mode_b = 1
        else:
            self._away_mode_b = None
        if self._away_mode_a is not None:
            self._away_state_a = (
                status.get(gw_vars.OTGW_GPIO_A_STATE) == self._away_mode_a
            )
        if self._away_mode_b is not None:
            self._away_state_b = (
                status.get(gw_vars.OTGW_GPIO_B_STATE) == self._away_mode_b
            )
        self.async_write_ha_state()

    @property
    def available(self):
        """Return availability of the sensor."""
        return self._available

    @property
    def name(self):
        """Return the friendly name."""
        return self.friendly_name

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._gateway.gw_id)},
            "name": self._gateway.name,
            "manufacturer": "Schelte Bron",
            "model": "OpenTherm Gateway",
            "sw_version": self._gateway.gw_version,
        }

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._gateway.gw_id

    @property
    def precision(self):
        """Return the precision of the system."""
        if self.temp_precision is not None and self.temp_precision != 0:
            return self.temp_precision
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_HALVES
        return PRECISION_WHOLE

    @property
    def should_poll(self):
        """Disable polling for this entity."""
        return False

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def hvac_action(self):
        """Return current HVAC operation."""
        return self._current_operation

    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return []

    def set_hvac_mode(self, hvac_mode):
        """Set the HVAC mode."""
        _LOGGER.warning("Changing HVAC mode is not supported")

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._current_temperature is None:
            return
        if self.floor_temp is True:
            if self.precision == PRECISION_HALVES:
                return int(2 * self._current_temperature) / 2
            if self.precision == PRECISION_TENTHS:
                return int(10 * self._current_temperature) / 10
            return int(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._new_target_temperature or self._target_temperature

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.precision

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self._away_state_a or self._away_state_b:
            return PRESET_AWAY
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Available preset modes to set."""
        return []

    def set_preset_mode(self, preset_mode):
        """Set the preset mode."""
        _LOGGER.warning("Changing preset mode is not supported")

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temp = float(kwargs[ATTR_TEMPERATURE])
            if temp == self.target_temperature:
                return
            self._new_target_temperature = await self._gateway.gateway.set_target_temp(
                temp
            )
            self.async_write_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return 1

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return 30
