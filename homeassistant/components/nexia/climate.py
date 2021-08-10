"""Support for Nexia / Trane XL thermostats."""
from nexia.const import (
    OPERATION_MODE_AUTO,
    OPERATION_MODE_COOL,
    OPERATION_MODE_HEAT,
    OPERATION_MODE_OFF,
    SYSTEM_STATUS_COOL,
    SYSTEM_STATUS_HEAT,
    SYSTEM_STATUS_IDLE,
    UNIT_FAHRENHEIT,
)
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import (
    ATTR_AIRCLEANER_MODE,
    ATTR_DEHUMIDIFY_SETPOINT,
    ATTR_DEHUMIDIFY_SUPPORTED,
    ATTR_HUMIDIFY_SETPOINT,
    ATTR_HUMIDIFY_SUPPORTED,
    ATTR_ZONE_STATUS,
    DOMAIN,
    NEXIA_DEVICE,
    SIGNAL_THERMOSTAT_UPDATE,
    SIGNAL_ZONE_UPDATE,
    UPDATE_COORDINATOR,
)
from .entity import NexiaThermostatZoneEntity
from .util import percent_conv

SERVICE_SET_AIRCLEANER_MODE = "set_aircleaner_mode"
SERVICE_SET_HUMIDIFY_SETPOINT = "set_humidify_setpoint"

SET_AIRCLEANER_SCHEMA = {
    vol.Required(ATTR_AIRCLEANER_MODE): cv.string,
}

SET_HUMIDITY_SCHEMA = {
    vol.Required(ATTR_HUMIDITY): vol.All(vol.Coerce(int), vol.Range(min=35, max=65)),
}


#
# Nexia has two bits to determine hvac mode
# There are actually eight states so we map to
# the most significant state
#
# 1. Zone Mode : Auto / Cooling / Heating / Off
# 2. Run Mode  : Hold / Run Schedule
#
#
HA_TO_NEXIA_HVAC_MODE_MAP = {
    HVAC_MODE_HEAT: OPERATION_MODE_HEAT,
    HVAC_MODE_COOL: OPERATION_MODE_COOL,
    HVAC_MODE_HEAT_COOL: OPERATION_MODE_AUTO,
    HVAC_MODE_AUTO: OPERATION_MODE_AUTO,
    HVAC_MODE_OFF: OPERATION_MODE_OFF,
}
NEXIA_TO_HA_HVAC_MODE_MAP = {
    value: key for key, value in HA_TO_NEXIA_HVAC_MODE_MAP.items()
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up climate for a Nexia device."""

    nexia_data = hass.data[DOMAIN][config_entry.entry_id]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        SERVICE_SET_HUMIDIFY_SETPOINT,
        SET_HUMIDITY_SCHEMA,
        SERVICE_SET_HUMIDIFY_SETPOINT,
    )
    platform.async_register_entity_service(
        SERVICE_SET_AIRCLEANER_MODE, SET_AIRCLEANER_SCHEMA, SERVICE_SET_AIRCLEANER_MODE
    )

    entities = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        for zone_id in thermostat.get_zone_ids():
            zone = thermostat.get_zone_by_id(zone_id)
            entities.append(NexiaZone(coordinator, zone))

    async_add_entities(entities, True)


class NexiaZone(NexiaThermostatZoneEntity, ClimateEntity):
    """Provides Nexia Climate support."""

    def __init__(self, coordinator, zone):
        """Initialize the thermostat."""
        super().__init__(
            coordinator, zone, name=zone.get_name(), unique_id=zone.zone_id
        )
        self._undo_humidfy_dispatcher = None
        self._undo_aircleaner_dispatcher = None
        # The has_* calls are stable for the life of the device
        # and do not do I/O
        self._has_relative_humidity = self._thermostat.has_relative_humidity()
        self._has_emergency_heat = self._thermostat.has_emergency_heat()
        self._has_humidify_support = self._thermostat.has_humidify_support()
        self._has_dehumidify_support = self._thermostat.has_dehumidify_support()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supported = (
            SUPPORT_TARGET_TEMPERATURE_RANGE
            | SUPPORT_TARGET_TEMPERATURE
            | SUPPORT_FAN_MODE
            | SUPPORT_PRESET_MODE
        )

        if self._has_humidify_support or self._has_dehumidify_support:
            supported |= SUPPORT_TARGET_HUMIDITY

        if self._has_emergency_heat:
            supported |= SUPPORT_AUX_HEAT

        return supported

    @property
    def is_fan_on(self):
        """Blower is on."""
        return self._thermostat.is_blower_active()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self._thermostat.get_unit() == "C" else TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._zone.get_temperature()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self._thermostat.get_fan_mode()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._thermostat.get_fan_modes()

    @property
    def min_temp(self):
        """Minimum temp for the current setting."""
        return (self._thermostat.get_setpoint_limits())[0]

    @property
    def max_temp(self):
        """Maximum temp for the current setting."""
        return (self._thermostat.get_setpoint_limits())[1]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self._thermostat.set_fan_mode(fan_mode)
        self._signal_thermostat_update()

    @property
    def preset_mode(self):
        """Preset that is active."""
        return self._zone.get_preset()

    @property
    def preset_modes(self):
        """All presets."""
        return self._zone.get_presets()

    def set_humidity(self, humidity):
        """Dehumidify target."""
        if self._thermostat.has_dehumidify_support():
            self._thermostat.set_dehumidify_setpoint(humidity / 100.0)
        else:
            self._thermostat.set_humidify_setpoint(humidity / 100.0)
        self._signal_thermostat_update()

    @property
    def target_humidity(self):
        """Humidity indoors setpoint."""
        if self._has_dehumidify_support:
            return percent_conv(self._thermostat.get_dehumidify_setpoint())
        if self._has_humidify_support:
            return percent_conv(self._thermostat.get_humidify_setpoint())
        return None

    @property
    def current_humidity(self):
        """Humidity indoors."""
        if self._has_relative_humidity:
            return percent_conv(self._thermostat.get_relative_humidity())
        return None

    @property
    def target_temperature(self):
        """Temperature we try to reach."""
        current_mode = self._zone.get_current_mode()

        if current_mode == OPERATION_MODE_COOL:
            return self._zone.get_cooling_setpoint()
        if current_mode == OPERATION_MODE_HEAT:
            return self._zone.get_heating_setpoint()
        return None

    @property
    def target_temperature_step(self):
        """Step size of temperature units."""
        if self._thermostat.get_unit() == UNIT_FAHRENHEIT:
            return 1.0
        return 0.5

    @property
    def target_temperature_high(self):
        """Highest temperature we are trying to reach."""
        current_mode = self._zone.get_current_mode()

        if current_mode in (OPERATION_MODE_COOL, OPERATION_MODE_HEAT):
            return None
        return self._zone.get_cooling_setpoint()

    @property
    def target_temperature_low(self):
        """Lowest temperature we are trying to reach."""
        current_mode = self._zone.get_current_mode()

        if current_mode in (OPERATION_MODE_COOL, OPERATION_MODE_HEAT):
            return None
        return self._zone.get_heating_setpoint()

    @property
    def hvac_action(self) -> str:
        """Operation ie. heat, cool, idle."""
        system_status = self._thermostat.get_system_status()
        zone_called = self._zone.is_calling()

        if self._zone.get_requested_mode() == OPERATION_MODE_OFF:
            return CURRENT_HVAC_OFF
        if not zone_called:
            return CURRENT_HVAC_IDLE
        if system_status == SYSTEM_STATUS_COOL:
            return CURRENT_HVAC_COOL
        if system_status == SYSTEM_STATUS_HEAT:
            return CURRENT_HVAC_HEAT
        if system_status == SYSTEM_STATUS_IDLE:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_IDLE

    @property
    def hvac_mode(self):
        """Return current mode, as the user-visible name."""
        mode = self._zone.get_requested_mode()
        hold = self._zone.is_in_permanent_hold()

        # If the device is in hold mode with
        # OPERATION_MODE_AUTO
        # overriding the schedule by still
        # heating and cooling to the
        # temp range.
        if hold and mode == OPERATION_MODE_AUTO:
            return HVAC_MODE_HEAT_COOL

        return NEXIA_TO_HA_HVAC_MODE_MAP[mode]

    @property
    def hvac_modes(self):
        """List of HVAC available modes."""
        return [
            HVAC_MODE_OFF,
            HVAC_MODE_AUTO,
            HVAC_MODE_HEAT_COOL,
            HVAC_MODE_HEAT,
            HVAC_MODE_COOL,
        ]

    def set_temperature(self, **kwargs):
        """Set target temperature."""
        new_heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        new_cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        set_temp = kwargs.get(ATTR_TEMPERATURE)

        deadband = self._thermostat.get_deadband()
        cur_cool_temp = self._zone.get_cooling_setpoint()
        cur_heat_temp = self._zone.get_heating_setpoint()
        (min_temp, max_temp) = self._thermostat.get_setpoint_limits()

        # Check that we're not going to hit any minimum or maximum values
        if new_heat_temp and new_heat_temp + deadband > max_temp:
            new_heat_temp = max_temp - deadband
        if new_cool_temp and new_cool_temp - deadband < min_temp:
            new_cool_temp = min_temp + deadband

        # Check that we're within the deadband range, fix it if we're not
        if (
            new_heat_temp
            and new_heat_temp != cur_heat_temp
            and new_cool_temp - new_heat_temp < deadband
        ):
            new_cool_temp = new_heat_temp + deadband

        if (
            new_cool_temp
            and new_cool_temp != cur_cool_temp
            and new_cool_temp - new_heat_temp < deadband
        ):
            new_heat_temp = new_cool_temp - deadband

        self._zone.set_heat_cool_temp(
            heat_temperature=new_heat_temp,
            cool_temperature=new_cool_temp,
            set_temperature=set_temp,
        )
        self._signal_zone_update()

    @property
    def is_aux_heat(self):
        """Emergency heat state."""
        return self._thermostat.is_emergency_heat_active()

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        data = super().extra_state_attributes

        data[ATTR_ZONE_STATUS] = self._zone.get_status()

        if not self._has_relative_humidity:
            return data

        min_humidity = percent_conv(self._thermostat.get_humidity_setpoint_limits()[0])
        max_humidity = percent_conv(self._thermostat.get_humidity_setpoint_limits()[1])
        data.update(
            {
                ATTR_MIN_HUMIDITY: min_humidity,
                ATTR_MAX_HUMIDITY: max_humidity,
                ATTR_DEHUMIDIFY_SUPPORTED: self._has_dehumidify_support,
                ATTR_HUMIDIFY_SUPPORTED: self._has_humidify_support,
            }
        )

        if self._has_dehumidify_support:
            dehumdify_setpoint = percent_conv(
                self._thermostat.get_dehumidify_setpoint()
            )
            data[ATTR_DEHUMIDIFY_SETPOINT] = dehumdify_setpoint

        if self._has_humidify_support:
            humdify_setpoint = percent_conv(self._thermostat.get_humidify_setpoint())
            data[ATTR_HUMIDIFY_SETPOINT] = humdify_setpoint

        return data

    def set_preset_mode(self, preset_mode: str):
        """Set the preset mode."""
        self._zone.set_preset(preset_mode)
        self._signal_zone_update()

    def turn_aux_heat_off(self):
        """Turn. Aux Heat off."""
        self._thermostat.set_emergency_heat(False)
        self._signal_thermostat_update()

    def turn_aux_heat_on(self):
        """Turn. Aux Heat on."""
        self._thermostat.set_emergency_heat(True)
        self._signal_thermostat_update()

    def turn_off(self):
        """Turn. off the zone."""
        self.set_hvac_mode(OPERATION_MODE_OFF)
        self._signal_zone_update()

    def turn_on(self):
        """Turn. on the zone."""
        self.set_hvac_mode(OPERATION_MODE_AUTO)
        self._signal_zone_update()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the system mode (Auto, Heat_Cool, Cool, Heat, etc)."""
        if hvac_mode == HVAC_MODE_AUTO:
            self._zone.call_return_to_schedule()
            self._zone.set_mode(mode=OPERATION_MODE_AUTO)
        else:
            self._zone.call_permanent_hold()
            self._zone.set_mode(mode=HA_TO_NEXIA_HVAC_MODE_MAP[hvac_mode])

        self.schedule_update_ha_state()

    def set_aircleaner_mode(self, aircleaner_mode):
        """Set the aircleaner mode."""
        self._thermostat.set_air_cleaner(aircleaner_mode)
        self._signal_thermostat_update()

    def set_humidify_setpoint(self, humidity):
        """Set the humidify setpoint."""
        self._thermostat.set_humidify_setpoint(humidity / 100.0)
        self._signal_thermostat_update()

    def _signal_thermostat_update(self):
        """Signal a thermostat update.

        Whenever the underlying library does an action against
        a thermostat, the data for the thermostat and all
        connected zone is updated.

        Update all the zones on the thermostat.
        """
        dispatcher_send(
            self.hass, f"{SIGNAL_THERMOSTAT_UPDATE}-{self._thermostat.thermostat_id}"
        )

    def _signal_zone_update(self):
        """Signal a zone update.

        Whenever the underlying library does an action against
        a zone, the data for the zone is updated.

        Update a single zone.
        """
        dispatcher_send(self.hass, f"{SIGNAL_ZONE_UPDATE}-{self._zone.zone_id}")
