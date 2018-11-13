"""
Support for Systemair Savecair climate devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.systemair_savecair/
"""
import voluptuous as vol

from homeassistant.components.climate import (
    PLATFORM_SCHEMA, STATE_AUTO, STATE_IDLE, STATE_MANUAL, SUPPORT_AWAY_MODE,
    SUPPORT_FAN_MODE, SUPPORT_ON_OFF, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE, ClimateDevice)
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_NAME, CONF_PASSWORD, TEMP_CELSIUS, TEMP_FAHRENHEIT)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-systemair-savecair==0.0.3']

ATTR_SUPPLY_AIR_TEMPERATURE = "supply_air_temperature"
ATTR_SUPPLY_AIR_FAN_SPEED = "supply_air_fan_speed"
ATTR_EXTRACT_AIR_FAN_SPEED = "extract_air_fan_speed"

FAN_OFF = "Off"
FAN_LOW = "Low"
FAN_NORMAL = "Medium"
FAN_HIGH = "High"

FAN_LIST = [FAN_OFF, FAN_LOW, FAN_NORMAL, FAN_HIGH]

OPERATION_LIST = [STATE_AUTO, STATE_MANUAL]

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | \
                SUPPORT_FAN_MODE | \
                SUPPORT_OPERATION_MODE | \
                SUPPORT_AWAY_MODE | \
                SUPPORT_ON_OFF

SAVECAIR_FAN_MODES = {
    1: FAN_OFF,
    2: FAN_LOW,
    3: FAN_NORMAL,
    4: FAN_HIGH
}

SAVECAIR_OPERATION_MODES = {
    0: STATE_AUTO,
    1: STATE_IDLE,
    2: STATE_MANUAL,
}

HA_OPERATION_MODES = {
    STATE_AUTO: 0,
    STATE_IDLE: 1,
    STATE_MANUAL: 2
}


CONF_IAM_ID = "iam_id"
DEFAULT_NAME = "SystemAIR"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_IAM_ID): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the SystemAIRplatform."""
    name = config[CONF_NAME]
    iam_id = config[CONF_IAM_ID]
    password = config[CONF_PASSWORD]

    # Create savecair client
    from systemair.savecair import SaveCairClient
    client = SaveCairClient(iam_id, password, loop=hass.loop)
    climate = SystemAIRClimate(client, name)
    async_add_entities([climate])


class SystemAIRClimate(ClimateDevice):
    """Representation of the climate sensor."""

    def __init__(self, client, name):
        """Construct the SystemAIR Climate Device."""
        self._name = name
        self._client = client
        self._client.start()

    async def async_update(self):
        """Retrieve latest state."""
        await self._client.update_sensors()

    async def async_added_to_hass(self):
        """Register update signal handler."""
        async def async_update_state():
            self.async_schedule_update_ha_state()
        self._client.cb_update.append(async_update_state)

    @property
    def device_state_attributes(self):
        """Update state attributes with additional attributes."""
        attributes = {
            ATTR_SUPPLY_AIR_TEMPERATURE: self.supply_air_temperature,
            ATTR_SUPPLY_AIR_FAN_SPEED: self.extract_air_fan_speed,
            ATTR_EXTRACT_AIR_FAN_SPEED: self.supply_air_fan_speed
        }
        attributes.update(self._client.data)
        return attributes

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._name

    @property
    def supply_air_fan_speed(self):
        """Return the supply air fan speed."""
        if "digital_input_tacho_saf_value" not in self._client.data:
            return None

        return self._client.data["digital_input_tacho_saf_value"]

    @property
    def extract_air_fan_speed(self):
        """Return the extract air fan speed."""
        if "digital_input_tacho_eaf_value" not in self._client.data:
            return None

        return self._client.data["digital_input_tacho_eaf_value"]

    @property
    def supply_air_temperature(self):
        """Return the supply air temperature."""
        if "supply_air_temp" not in self._client.data:
            return None

        air_temperature = self._client.data["supply_air_temp"]

        if air_temperature is None:
            return None

        return air_temperature / 10

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
        if "pdm_input_temp_value" not in self._client.data:
            return None

        current_temperature = self._client.data["pdm_input_temp_value"]

        if current_temperature is None:
            return None

        return current_temperature / 10

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if "main_temperature_offset" not in self._client.data:
            return None

        target_temperature = self._client.data["main_temperature_offset"]

        if target_temperature is None:
            return None

        return target_temperature / 10

    @property
    def current_humidity(self):
        """Return the current humidity."""
        if "rh_sensor" not in self._client.data:
            return None

        return self._client.data["rh_sensor"]

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        if "main_airflow" not in self._client.data:
            return None

        if self._client.data["main_airflow"] is None:
            return None

        fan_mode = int(self._client.data["main_airflow"])
        ha_fan_mode = SAVECAIR_FAN_MODES[fan_mode]

        return ha_fan_mode

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        mode = self._client.get_current_operation()
        if mode is None:
            return None

        return SAVECAIR_OPERATION_MODES[mode]

    @property
    def is_on(self):
        """Return true if the device is on."""
        if "main_airflow" not in self._client.data:
            return True

        if self._client.data["main_airflow"] is None:
            return False
        airflow = self._client.data["main_airflow"]

        if airflow is not None:
            return int(self._client.data["main_airflow"]) - 1 > 0

        return False

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        if self.current_operation != STATE_MANUAL:
            return None

        return FAN_LIST

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        await self._client.set_temperature(int(temperature))

    async def async_set_fan_mode(self, fan_mode):
        """Set new target temperature."""
        await self._client.set_fan_mode(fan_mode)

    async def async_set_operation_mode(self, operation_mode):
        """Set the operation mode."""
        mode = HA_OPERATION_MODES[operation_mode]

        await self._client.set_operation_mode(mode)

    async def async_turn_on(self):
        """Turn on the climate device."""
        await self._client.set_fan_high()

    async def async_turn_off(self):
        """Turn of the climate decive."""
        await self._client.set_manual_mode()
        await self._client.set_fan_off()

    async def async_turn_away_mode_on(self):
        """Turn the climate device away mode on."""
        await self._client.set_away_mode()

    async def async_turn_away_mode_off(self):
        """Turn the climate device away mode on."""
        await self._client.set_auto_mode()

    @property
    def is_away_mode_on(self):
        """Flag to determine if the device is away."""
        return self.current_operation == STATE_IDLE
