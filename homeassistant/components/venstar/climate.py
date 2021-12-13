"""Support for Venstar WiFi Thermostats."""
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA, ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_NONE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    PRECISION_HALVES,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VenstarDataUpdateCoordinator, VenstarEntity
from .const import (
    _LOGGER,
    ATTR_FAN_STATE,
    ATTR_HVAC_STATE,
    CONF_HUMIDIFIER,
    DEFAULT_SSL,
    DOMAIN,
    HOLD_MODE_TEMPERATURE,
    VALID_FAN_STATES,
    VALID_THERMOSTAT_MODES,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_HUMIDIFIER, default=True): cv.boolean,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=5): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PIN): cv.string,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venstar thermostat."""
    venstar_data_coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        [
            VenstarThermostat(
                venstar_data_coordinator,
                config_entry,
            )
        ],
    )


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Venstar thermostat platform.

    Venstar uses config flow for configuration now. If an entry exists in
    configuration.yaml, the import flow will attempt to import it and create
    a config entry.
    """
    _LOGGER.warning(
        "Loading venstar via platform config is deprecated; The configuration"
        " has been migrated to a config entry and can be safely removed"
    )
    # No config entry exists and configuration.yaml config exists, trigger the import flow.
    if not hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )


class VenstarThermostat(VenstarEntity, ClimateEntity):
    """Representation of a Venstar thermostat."""

    def __init__(
        self,
        venstar_data_coordinator: VenstarDataUpdateCoordinator,
        config: ConfigEntry,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__(venstar_data_coordinator, config)
        self._mode_map = {
            HVAC_MODE_HEAT: self._client.MODE_HEAT,
            HVAC_MODE_COOL: self._client.MODE_COOL,
            HVAC_MODE_AUTO: self._client.MODE_AUTO,
        }
        self._attr_unique_id = config.entry_id
        self._attr_name = self._client.name

    @property
    def supported_features(self):
        """Return the list of supported features."""
        features = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE

        if self._client.mode == self._client.MODE_AUTO:
            features |= SUPPORT_TARGET_TEMPERATURE_RANGE

        if self._client.hum_setpoint is not None:
            features |= SUPPORT_TARGET_HUMIDITY

        return features

    @property
    def precision(self):
        """Return the precision of the system.

        Venstar temperature values are passed back and forth in the
        API in C or F, with half-degree accuracy.
        """
        return PRECISION_HALVES

    @property
    def temperature_unit(self):
        """Return the unit of measurement, as defined by the API."""
        if self._client.tempunits == self._client.TEMPUNITS_F:
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return VALID_FAN_STATES

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return VALID_THERMOSTAT_MODES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._client.get_indoor_temp()

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._client.get_indoor_humidity()

    @property
    def hvac_mode(self):
        """Return current operation mode ie. heat, cool, auto."""
        if self._client.mode == self._client.MODE_HEAT:
            return HVAC_MODE_HEAT
        if self._client.mode == self._client.MODE_COOL:
            return HVAC_MODE_COOL
        if self._client.mode == self._client.MODE_AUTO:
            return HVAC_MODE_AUTO
        return HVAC_MODE_OFF

    @property
    def hvac_action(self):
        """Return current operation mode ie. heat, cool, auto."""
        if self._client.state == self._client.STATE_IDLE:
            return CURRENT_HVAC_IDLE
        if self._client.state == self._client.STATE_HEATING:
            return CURRENT_HVAC_HEAT
        if self._client.state == self._client.STATE_COOLING:
            return CURRENT_HVAC_COOL
        return CURRENT_HVAC_OFF

    @property
    def fan_mode(self):
        """Return the current fan mode."""
        if self._client.fan == self._client.FAN_ON:
            return FAN_ON
        return FAN_AUTO

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        return {
            ATTR_FAN_STATE: self._client.fanstate,
            ATTR_HVAC_STATE: self._client.state,
        }

    @property
    def target_temperature(self):
        """Return the target temperature we try to reach."""
        if self._client.mode == self._client.MODE_HEAT:
            return self._client.heattemp
        if self._client.mode == self._client.MODE_COOL:
            return self._client.cooltemp
        return None

    @property
    def target_temperature_low(self):
        """Return the lower bound temp if auto mode is on."""
        if self._client.mode == self._client.MODE_AUTO:
            return self._client.heattemp
        return None

    @property
    def target_temperature_high(self):
        """Return the upper bound temp if auto mode is on."""
        if self._client.mode == self._client.MODE_AUTO:
            return self._client.cooltemp
        return None

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._client.hum_setpoint

    @property
    def min_humidity(self):
        """Return the minimum humidity. Hardcoded to 0 in API."""
        return 0

    @property
    def max_humidity(self):
        """Return the maximum humidity. Hardcoded to 60 in API."""
        return 60

    @property
    def preset_mode(self):
        """Return current preset."""
        if self._client.away:
            return PRESET_AWAY
        if self._client.schedule == 0:
            return HOLD_MODE_TEMPERATURE
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return valid preset modes."""
        return [PRESET_NONE, PRESET_AWAY, HOLD_MODE_TEMPERATURE]

    def _set_operation_mode(self, operation_mode):
        """Change the operation mode (internal)."""
        if operation_mode == HVAC_MODE_HEAT:
            success = self._client.set_mode(self._client.MODE_HEAT)
        elif operation_mode == HVAC_MODE_COOL:
            success = self._client.set_mode(self._client.MODE_COOL)
        elif operation_mode == HVAC_MODE_AUTO:
            success = self._client.set_mode(self._client.MODE_AUTO)
        else:
            success = self._client.set_mode(self._client.MODE_OFF)

        if not success:
            _LOGGER.error("Failed to change the operation mode")
        return success

    def set_temperature(self, **kwargs):
        """Set a new target temperature."""
        set_temp = True
        operation_mode = kwargs.get(ATTR_HVAC_MODE)
        temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)
        temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temperature = kwargs.get(ATTR_TEMPERATURE)

        if operation_mode and self._mode_map.get(operation_mode) != self._client.mode:
            set_temp = self._set_operation_mode(operation_mode)

        if set_temp:
            if (
                self._mode_map.get(operation_mode, self._client.mode)
                == self._client.MODE_HEAT
            ):
                success = self._client.set_setpoints(temperature, self._client.cooltemp)
            elif (
                self._mode_map.get(operation_mode, self._client.mode)
                == self._client.MODE_COOL
            ):
                success = self._client.set_setpoints(self._client.heattemp, temperature)
            elif (
                self._mode_map.get(operation_mode, self._client.mode)
                == self._client.MODE_AUTO
            ):
                success = self._client.set_setpoints(temp_low, temp_high)
            else:
                success = False
                _LOGGER.error(
                    "The thermostat is currently not in a mode "
                    "that supports target temperature: %s",
                    operation_mode,
                )

            if not success:
                _LOGGER.error("Failed to change the temperature")
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        if fan_mode == STATE_ON:
            success = self._client.set_fan(self._client.FAN_ON)
        else:
            success = self._client.set_fan(self._client.FAN_AUTO)

        if not success:
            _LOGGER.error("Failed to change the fan mode")
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        self._set_operation_mode(hvac_mode)
        self.schedule_update_ha_state()

    def set_humidity(self, humidity):
        """Set new target humidity."""
        success = self._client.set_hum_setpoint(humidity)

        if not success:
            _LOGGER.error("Failed to change the target humidity level")
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode):
        """Set the hold mode."""
        if preset_mode == PRESET_AWAY:
            success = self._client.set_away(self._client.AWAY_AWAY)
        elif preset_mode == HOLD_MODE_TEMPERATURE:
            success = self._client.set_away(self._client.AWAY_HOME)
            success = success and self._client.set_schedule(0)
        elif preset_mode == PRESET_NONE:
            success = self._client.set_away(self._client.AWAY_HOME)
            success = success and self._client.set_schedule(1)
        else:
            _LOGGER.error("Unknown hold mode: %s", preset_mode)
            success = False

        if not success:
            _LOGGER.error("Failed to change the schedule/hold state")
        self.schedule_update_ha_state()
