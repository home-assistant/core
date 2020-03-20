"""Support for Nexia / Trane XL thermostats."""
import logging

from nexia.const import (
    FAN_MODES,
    OPERATION_MODE_AUTO,
    OPERATION_MODE_COOL,
    OPERATION_MODE_HEAT,
    OPERATION_MODE_OFF,
    SYSTEM_STATUS_COOL,
    SYSTEM_STATUS_HEAT,
    SYSTEM_STATUS_IDLE,
    UNIT_FAHRENHEIT,
)

from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
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
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_TEMPERATURE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from .const import (
    ATTR_DEHUMIDIFY_SETPOINT,
    ATTR_DEHUMIDIFY_SUPPORTED,
    ATTR_HUMIDIFY_SETPOINT,
    ATTR_HUMIDIFY_SUPPORTED,
    ATTR_ZONE_STATUS,
    ATTRIBUTION,
    DATA_NEXIA,
    DOMAIN,
    MANUFACTURER,
    NEXIA_DEVICE,
    UPDATE_COORDINATOR,
)
from .entity import NexiaEntity

_LOGGER = logging.getLogger(__name__)

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

    nexia_data = hass.data[DOMAIN][config_entry.entry_id][DATA_NEXIA]
    nexia_home = nexia_data[NEXIA_DEVICE]
    coordinator = nexia_data[UPDATE_COORDINATOR]

    entities = []
    for thermostat_id in nexia_home.get_thermostat_ids():
        thermostat = nexia_home.get_thermostat_by_id(thermostat_id)
        for zone_id in thermostat.get_zone_ids():
            zone = thermostat.get_zone_by_id(zone_id)
            entities.append(NexiaZone(coordinator, zone))

    async_add_entities(entities, True)


class NexiaZone(NexiaEntity, ClimateDevice):
    """Provides Nexia Climate support."""

    def __init__(self, coordinator, device):
        """Initialize the thermostat."""
        super().__init__(coordinator)
        self.thermostat = device.thermostat
        self._device = device
        self._coordinator = coordinator
        # The has_* calls are stable for the life of the device
        # and do not do I/O
        self._has_relative_humidity = self.thermostat.has_relative_humidity()
        self._has_emergency_heat = self.thermostat.has_emergency_heat()
        self._has_humidify_support = self.thermostat.has_humidify_support()
        self._has_dehumidify_support = self.thermostat.has_dehumidify_support()

    @property
    def unique_id(self):
        """Device Uniqueid."""
        return self._device.zone_id

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
        return self.thermostat.is_blower_active()

    @property
    def name(self):
        """Name of the zone."""
        return self._device.get_name()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS if self.thermostat.get_unit() == "C" else TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._device.get_temperature()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.thermostat.get_fan_mode()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return FAN_MODES

    @property
    def min_temp(self):
        """Minimum temp for the current setting."""
        return (self._device.thermostat.get_setpoint_limits())[0]

    @property
    def max_temp(self):
        """Maximum temp for the current setting."""
        return (self._device.thermostat.get_setpoint_limits())[1]

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self.thermostat.set_fan_mode(fan_mode)
        self.schedule_update_ha_state()

    @property
    def preset_mode(self):
        """Preset that is active."""
        return self._device.get_preset()

    @property
    def preset_modes(self):
        """All presets."""
        return self._device.get_presets()

    def set_humidity(self, humidity):
        """Dehumidify target."""
        self.thermostat.set_dehumidify_setpoint(humidity / 100.0)
        self.schedule_update_ha_state()

    @property
    def target_humidity(self):
        """Humidity indoors setpoint."""
        if self._has_dehumidify_support:
            return round(self.thermostat.get_dehumidify_setpoint() * 100.0, 1)
        if self._has_humidify_support:
            return round(self.thermostat.get_humidify_setpoint() * 100.0, 1)
        return None

    @property
    def current_humidity(self):
        """Humidity indoors."""
        if self._has_relative_humidity:
            return round(self.thermostat.get_relative_humidity() * 100.0, 1)
        return None

    @property
    def target_temperature(self):
        """Temperature we try to reach."""
        current_mode = self._device.get_current_mode()

        if current_mode == OPERATION_MODE_COOL:
            return self._device.get_cooling_setpoint()
        if current_mode == OPERATION_MODE_HEAT:
            return self._device.get_heating_setpoint()
        return None

    @property
    def target_temperature_step(self):
        """Step size of temperature units."""
        if self._device.thermostat.get_unit() == UNIT_FAHRENHEIT:
            return 1.0
        return 0.5

    @property
    def target_temperature_high(self):
        """Highest temperature we are trying to reach."""
        current_mode = self._device.get_current_mode()

        if current_mode in (OPERATION_MODE_COOL, OPERATION_MODE_HEAT):
            return None
        return self._device.get_cooling_setpoint()

    @property
    def target_temperature_low(self):
        """Lowest temperature we are trying to reach."""
        current_mode = self._device.get_current_mode()

        if current_mode in (OPERATION_MODE_COOL, OPERATION_MODE_HEAT):
            return None
        return self._device.get_heating_setpoint()

    @property
    def hvac_action(self) -> str:
        """Operation ie. heat, cool, idle."""
        system_status = self.thermostat.get_system_status()
        zone_called = self._device.is_calling()

        if self._device.get_requested_mode() == OPERATION_MODE_OFF:
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
        mode = self._device.get_requested_mode()
        hold = self._device.is_in_permanent_hold()

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
        new_heat_temp = kwargs.get(ATTR_TARGET_TEMP_LOW, None)
        new_cool_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH, None)
        set_temp = kwargs.get(ATTR_TEMPERATURE, None)

        deadband = self.thermostat.get_deadband()
        cur_cool_temp = self._device.get_cooling_setpoint()
        cur_heat_temp = self._device.get_heating_setpoint()
        (min_temp, max_temp) = self.thermostat.get_setpoint_limits()

        # Check that we're not going to hit any minimum or maximum values
        if new_heat_temp and new_heat_temp + deadband > max_temp:
            new_heat_temp = max_temp - deadband
        if new_cool_temp and new_cool_temp - deadband < min_temp:
            new_cool_temp = min_temp + deadband

        # Check that we're within the deadband range, fix it if we're not
        if new_heat_temp and new_heat_temp != cur_heat_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_cool_temp = new_heat_temp + deadband
        if new_cool_temp and new_cool_temp != cur_cool_temp:
            if new_cool_temp - new_heat_temp < deadband:
                new_heat_temp = new_cool_temp - deadband

        self._device.set_heat_cool_temp(
            heat_temperature=new_heat_temp,
            cool_temperature=new_cool_temp,
            set_temperature=set_temp,
        )
        self.schedule_update_ha_state()

    @property
    def is_aux_heat(self):
        """Emergency heat state."""
        return self.thermostat.is_emergency_heat_active()

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._device.zone_id)},
            "name": self._device.get_name(),
            "model": self.thermostat.get_model(),
            "sw_version": self.thermostat.get_firmware(),
            "manufacturer": MANUFACTURER,
            "via_device": (DOMAIN, self.thermostat.thermostat_id),
        }

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        data = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_ZONE_STATUS: self._device.get_status(),
        }

        if self._has_relative_humidity:
            data.update(
                {
                    ATTR_HUMIDIFY_SUPPORTED: self._has_humidify_support,
                    ATTR_DEHUMIDIFY_SUPPORTED: self._has_dehumidify_support,
                    ATTR_MIN_HUMIDITY: round(
                        self.thermostat.get_humidity_setpoint_limits()[0] * 100.0, 1,
                    ),
                    ATTR_MAX_HUMIDITY: round(
                        self.thermostat.get_humidity_setpoint_limits()[1] * 100.0, 1,
                    ),
                }
            )
            if self._has_dehumidify_support:
                data.update(
                    {
                        ATTR_DEHUMIDIFY_SETPOINT: round(
                            self.thermostat.get_dehumidify_setpoint() * 100.0, 1
                        ),
                    }
                )
            if self._has_humidify_support:
                data.update(
                    {
                        ATTR_HUMIDIFY_SETPOINT: round(
                            self.thermostat.get_humidify_setpoint() * 100.0, 1
                        )
                    }
                )
        return data

    def set_preset_mode(self, preset_mode: str):
        """Set the preset mode."""
        self._device.set_preset(preset_mode)
        self.schedule_update_ha_state()

    def turn_aux_heat_off(self):
        """Turn. Aux Heat off."""
        self.thermostat.set_emergency_heat(False)
        self.schedule_update_ha_state()

    def turn_aux_heat_on(self):
        """Turn. Aux Heat on."""
        self.thermostat.set_emergency_heat(True)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn. off the zone."""
        self.set_hvac_mode(OPERATION_MODE_OFF)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn. on the zone."""
        self.set_hvac_mode(OPERATION_MODE_AUTO)
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set the system mode (Auto, Heat_Cool, Cool, Heat, etc)."""
        if hvac_mode == HVAC_MODE_AUTO:
            self._device.call_return_to_schedule()
            self._device.set_mode(mode=OPERATION_MODE_AUTO)
        else:
            self._device.call_permanent_hold()
            self._device.set_mode(mode=HA_TO_NEXIA_HVAC_MODE_MAP[hvac_mode])

        self.schedule_update_ha_state()

    def set_aircleaner_mode(self, aircleaner_mode):
        """Set the aircleaner mode."""
        self.thermostat.set_air_cleaner(aircleaner_mode)
        self.schedule_update_ha_state()

    def set_humidify_setpoint(self, humidify_setpoint):
        """Set the humidify setpoint."""
        self.thermostat.set_humidify_setpoint(humidify_setpoint / 100.0)
        self.schedule_update_ha_state()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()
