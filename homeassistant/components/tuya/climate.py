"""Support for the Tuya climate devices."""
from datetime import timedelta
import logging

from homeassistant.components.climate import (
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PLATFORM,
    CONF_UNIT_OF_MEASUREMENT,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import TuyaDevice
from .const import (
    CONF_CURR_TEMP_DIVIDER,
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_TEMP_DIVIDER,
    DOMAIN,
    SIGNAL_CONFIG_ENTITY,
    TUYA_DATA,
    TUYA_DISCOVERY_NEW,
)

DEVICE_TYPE = "climate"

SCAN_INTERVAL = timedelta(seconds=15)

HA_STATE_TO_TUYA = {
    HVAC_MODE_AUTO: "auto",
    HVAC_MODE_COOL: "cold",
    HVAC_MODE_FAN_ONLY: "wind",
    HVAC_MODE_HEAT: "hot",
}

TUYA_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_TUYA.items()}

FAN_MODES = {FAN_LOW, FAN_MEDIUM, FAN_HIGH}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up tuya sensors dynamically through tuya discovery."""

    platform = config_entry.data[CONF_PLATFORM]

    async def async_discover_sensor(dev_ids):
        """Discover and add a discovered tuya sensor."""
        if not dev_ids:
            return
        entities = await hass.async_add_executor_job(
            _setup_entities,
            hass,
            dev_ids,
            platform,
        )
        async_add_entities(entities)

    async_dispatcher_connect(
        hass, TUYA_DISCOVERY_NEW.format(SENSOR_DOMAIN), async_discover_sensor
    )

    devices_ids = hass.data[DOMAIN]["pending"].pop(SENSOR_DOMAIN)
    await async_discover_sensor(devices_ids)


def _setup_entities(hass, dev_ids, platform):
    """Set up Tuya Climate device."""
    tuya = hass.data[DOMAIN][TUYA_DATA]
    entities = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        entities.append(TuyaClimateEntity(device, platform))
    return entities


class TuyaClimateEntity(TuyaDevice, ClimateEntity):
    """Tuya climate devices,include air conditioner,heater."""

    def __init__(self, tuya, platform):
        """Init climate device."""
        super().__init__(tuya, platform)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self.operations = [HVAC_MODE_OFF]
        self._has_operation = False
        self._def_hvac_mode = HVAC_MODE_AUTO
        self._min_temp = None
        self._max_temp = None

    @callback
    def _process_config(self):
        """Set device config parameter."""
        config = self._get_device_config()
        if not config:
            return
        unit = config.get(CONF_UNIT_OF_MEASUREMENT)
        if unit:
            self._tuya.set_unit("FAHRENHEIT" if unit == TEMP_FAHRENHEIT else "CELSIUS")
        self._tuya.temp_divider = config.get(CONF_TEMP_DIVIDER, 0)
        self._tuya.curr_temp_divider = config.get(CONF_CURR_TEMP_DIVIDER, 0)
        min_temp = config.get(CONF_MIN_TEMP, 0)
        max_temp = config.get(CONF_MAX_TEMP, 0)
        if min_temp >= max_temp:
            self._min_temp = self._max_temp = None
        else:
            self._min_temp = min_temp
            self._max_temp = max_temp

    async def async_added_to_hass(self):
        """Create operation list when add to hass."""
        await super().async_added_to_hass()
        self._process_config()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTITY, self._process_config
            )
        )

        modes = self._tuya.operation_list()
        if modes is None:
            if self._def_hvac_mode not in self.operations:
                self.operations.append(self._def_hvac_mode)
            return

        for mode in modes:
            if mode not in TUYA_STATE_TO_HA:
                continue
            ha_mode = TUYA_STATE_TO_HA[mode]
            if ha_mode not in self.operations:
                self.operations.append(ha_mode)
            self._has_operation = True

    @property
    def precision(self):
        """Return the precision of the system."""
        if self._tuya.has_decimal():
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        unit = self._tuya.temperature_unit()
        if unit == "FAHRENHEIT":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if not self._tuya.state():
            return HVAC_MODE_OFF

        if not self._has_operation:
            return self._def_hvac_mode

        mode = self._tuya.current_operation()
        if mode is None:
            return None
        return TUYA_STATE_TO_HA.get(mode)

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return self.operations

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._tuya.current_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._tuya.target_temperature()

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self._tuya.target_temperature_step()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._tuya.current_fan_mode()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._tuya.fan_list()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self._tuya.set_temperature(kwargs[ATTR_TEMPERATURE])

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self._tuya.set_fan_mode(fan_mode)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self._tuya.turn_off()
            return

        if not self._tuya.state():
            self._tuya.turn_on()

        if self._has_operation:
            self._tuya.set_operation_mode(HA_STATE_TO_TUYA.get(hvac_mode))

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = 0
        if self._tuya.support_target_temperature():
            supports = supports | SUPPORT_TARGET_TEMPERATURE
        if self._tuya.support_wind_speed():
            supports = supports | SUPPORT_FAN_MODE
        return supports

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        min_temp = (
            self._min_temp if self._min_temp is not None else self._tuya.min_temp()
        )
        if min_temp is not None:
            return min_temp
        return super().min_temp

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        max_temp = (
            self._max_temp if self._max_temp is not None else self._tuya.max_temp()
        )
        if max_temp is not None:
            return max_temp
        return super().max_temp
