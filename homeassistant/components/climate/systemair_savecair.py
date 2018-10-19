"""
SystemAIR platform for VTR 300 Ventilation Unit.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/savecair/
"""
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA, SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_DEVICE, CONF_NAME, CONF_PASSWORD,
    CONF_SCAN_INTERVAL, TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['websockets==6.0', 'python-systemair-savecair==0.0.2']

ATTR_SUPPLY_AIR_TEMPERATURE = "supply_air_temperature"
ATTR_SUPPLY_AIR_FAN_SPEED = "supply_air_fan_speed"
ATTR_EXTRACT_AIR_FAN_SPEED = "extract_air_fan_speed"

CONF_IAM_ID = "iam_id"

DEFAULT_NAME = "SystemAIR"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_DEVICE): cv.string,
    vol.Required(CONF_IAM_ID): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the SystemAIR platform."""
    name = config.get(CONF_NAME)
    device = config.get(CONF_DEVICE)
    iam_id = config.get(CONF_IAM_ID)
    password = config.get(CONF_PASSWORD)

    climate = SystemAIRClimate(name, device, iam_id, password)
    async_add_entities([climate])


class SystemAIRClimate(ClimateDevice):
    """Representation of the climate sensor."""

    def __init__(self, name, unit, iam_id, password):
        """Construct the SystemAIR Climate Device."""
        from systemair.savecair.client import SavecairClient
        self._name = name

        """Initialize the climate device."""
        self._support_flags = SUPPORT_TARGET_TEMPERATURE

        if unit == "vtr_300":
            self._support_flags = self._support_flags | SUPPORT_FAN_MODE
            self._support_flags = self._support_flags | SUPPORT_OPERATION_MODE
            self._support_flags = self._support_flags | SUPPORT_ON_OFF

        # Create savecair client
        self._client = SavecairClient(iam_id, password)
        self._client.update_cb.append(self.update_callback)
        self.last_operation_mode = None

        self._fan_list = ['Off', 'Low', 'Normal', 'High']
        self._operation_list = ['Auto', 'Manual', 'Crowded',
                                'Refresh', 'Fireplace', 'Away', 'Holiday']

    def update_callback(self):
        """Update the state."""
        self.schedule_update_ha_state()

    async def async_update(self):
        """Retrieve latest state."""
        await self._client.update_sensors()
        self.schedule_update_ha_state()

    @property
    def state_attributes(self):
        """Update state attributes with additional attributes."""
        attributes = super().state_attributes
        attributes.update({
            ATTR_SUPPLY_AIR_TEMPERATURE: self.supply_air_temperature,
            ATTR_SUPPLY_AIR_FAN_SPEED: self.extract_air_fan_speed,
            ATTR_EXTRACT_AIR_FAN_SPEED: self.supply_air_fan_speed
        })
        attributes.update(self._client.data)
        return attributes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def supply_air_fan_speed(self):
        """Return the supply air fan speed."""
        return self._client.data["digital_input_tacho_saf_value"] \
            if "digital_input_tacho_saf_value" in self._client.data else None

    @property
    def extract_air_fan_speed(self):
        """Return the extract air fan speed."""
        return self._client.data["digital_input_tacho_eaf_value"] \
            if "digital_input_tacho_eaf_value" in self._client.data else None

    @property
    def supply_air_temperature(self):
        """Return the supply air temperature."""
        return self._client.data["supply_air_temp"] / 10 \
            if "supply_air_temp" in self._client.data else None

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if "control_regulation_temp_unit" not in self._client.data:
            return TEMP_CELSIUS

        if self._client.data["control_regulation_temp_unit"] == "celsius":
            return TEMP_CELSIUS

        return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.data["pdm_input_temp_value"] / 10 \
            if "pdm_input_temp_value" in self._client.data else None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._client.data["main_temperature_offset"] / 10 \
            if "main_temperature_offset" in self._client.data else None

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._client.data["rh_sensor"] \
            if "rh_sensor" in self._client.data else None

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if "main_airflow" not in self._client.data:
            return None

        return self._fan_list[int(self._client.data["main_airflow"]) - 1]

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        if "main_user_mode" not in self._client.data:
            return None

        return self._operation_list[
            int(self._client.data["main_user_mode"])
        ]

    @property
    def is_on(self):
        """Return true if the device is on."""
        if "main_airflow" not in self._client.data:
            return True

        return int(self._client.data["main_airflow"]) - 1 > 0

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        if self.current_operation == "Manual":
            return self._fan_list
        return None

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        self.hass.async_create_task(self._client.set_temperature(temperature))

    def set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        if fan_mode == "Off":
            self.hass.async_create_task(self._client.set_fan_off())
        elif fan_mode == "Low":
            self.hass.async_create_task(self._client.set_fan_low())
        elif fan_mode == "Normal":
            self.hass.async_create_task(self._client.set_fan_normal())
        elif fan_mode == "Maximum":
            self.hass.async_create_task(self._client.set_fan_high())

    def set_operation_mode(self, operation_mode):
        """Set the operation mode."""
        if self.last_operation_mode == "Fireplace":
            self.hass.async_create_task(self._client.set_manual_mode())

        if operation_mode == "Auto":
            self.hass.async_create_task(self._client.set_auto_mode())
        elif operation_mode == "Manual":
            self.hass.async_create_task(self._client.set_manual_mode())
        elif operation_mode == "Crowded":
            self.hass.async_create_task(self._client.set_crowded_mode())
        elif operation_mode == "Refresh":
            self.hass.async_create_task(self._client.set_refresh_mode())
        elif operation_mode == "Fireplace":
            self.hass.async_create_task(self._client.set_fireplace_mode())
        elif operation_mode == "Away":
            self.hass.async_create_task(self._client.set_away_mode())
        elif operation_mode == "Holiday":
            self.hass.async_create_task(self._client.set_holiday_mode())

        self.last_operation_mode = operation_mode

    def turn_on(self):
        """Turn on the climate device."""
        self.hass.async_create_task(self._client.set_fan_high())

    def turn_off(self):
        """Turn of the climate decive."""
        self.hass.async_create_task(self._client.set_manual_mode())
        self.hass.async_create_task(self._client.set_fan_off())
