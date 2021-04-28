"""Support for AVM Fritz!Box smarthome thermostate devices."""
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_COMFORT,
    PRESET_ECO,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    PRECISION_HALVES,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import AddEntitiesCallback

from . import FritzBoxEntity
from .const import (
    ATTR_STATE_BATTERY_LOW,
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_HOLIDAY_MODE,
    ATTR_STATE_LOCKED,
    ATTR_STATE_SUMMER_MODE,
    ATTR_STATE_WINDOW_OPEN,
    CONF_COORDINATOR,
    DOMAIN as FRITZBOX_DOMAIN,
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

OPERATION_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

MIN_TEMPERATURE = 8
MAX_TEMPERATURE = 28

PRESET_MANUAL = "manual"

# special temperatures for on/off in Fritz!Box API (modified by pyfritzhome)
ON_API_TEMPERATURE = 127.0
OFF_API_TEMPERATURE = 126.5
ON_REPORT_SET_TEMPERATURE = 30.0
OFF_REPORT_SET_TEMPERATURE = 0.0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Fritzbox smarthome thermostat from ConfigEntry."""
    entities = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if not device.has_thermostat:
            continue

        entities.append(
            FritzboxThermostat(
                {
                    ATTR_NAME: f"{device.name}",
                    ATTR_ENTITY_ID: f"{device.ain}",
                    ATTR_UNIT_OF_MEASUREMENT: None,
                    ATTR_DEVICE_CLASS: None,
                },
                coordinator,
                ain,
            )
        )

    async_add_entities(entities)


class FritzboxThermostat(FritzBoxEntity, ClimateEntity):
    """The thermostat class for Fritzbox smarthome thermostates."""

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def available(self):
        """Return if thermostat is available."""
        return self.device.present

    @property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return TEMP_CELSIUS

    @property
    def precision(self):
        """Return precision 0.5."""
        return PRECISION_HALVES

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.actual_temperature

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        if self.device.target_temperature == ON_API_TEMPERATURE:
            return ON_REPORT_SET_TEMPERATURE
        if self.device.target_temperature == OFF_API_TEMPERATURE:
            return OFF_REPORT_SET_TEMPERATURE
        return self.device.target_temperature

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_HVAC_MODE in kwargs:
            hvac_mode = kwargs.get(ATTR_HVAC_MODE)
            await self.async_set_hvac_mode(hvac_mode)
        elif ATTR_TEMPERATURE in kwargs:
            temperature = kwargs.get(ATTR_TEMPERATURE)
            await self.hass.async_add_executor_job(
                self.device.set_target_temperature, temperature
            )
        await self.coordinator.async_refresh()

    @property
    def hvac_mode(self):
        """Return the current operation mode."""
        if (
            self.device.target_temperature == OFF_REPORT_SET_TEMPERATURE
            or self.device.target_temperature == OFF_API_TEMPERATURE
        ):
            return HVAC_MODE_OFF

        return HVAC_MODE_HEAT

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return OPERATION_LIST

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_set_temperature(temperature=OFF_REPORT_SET_TEMPERATURE)
        else:
            await self.async_set_temperature(
                temperature=self.device.comfort_temperature
            )

    @property
    def preset_mode(self):
        """Return current preset mode."""
        if self.device.target_temperature == self.device.comfort_temperature:
            return PRESET_COMFORT
        if self.device.target_temperature == self.device.eco_temperature:
            return PRESET_ECO

    @property
    def preset_modes(self):
        """Return supported preset modes."""
        return [PRESET_ECO, PRESET_COMFORT]

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode."""
        if preset_mode == PRESET_COMFORT:
            await self.async_set_temperature(
                temperature=self.device.comfort_temperature
            )
        elif preset_mode == PRESET_ECO:
            await self.async_set_temperature(temperature=self.device.eco_temperature)

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return MIN_TEMPERATURE

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return MAX_TEMPERATURE

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        attrs = {
            ATTR_STATE_BATTERY_LOW: self.device.battery_low,
            ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
            ATTR_STATE_LOCKED: self.device.lock,
        }

        # the following attributes are available since fritzos 7
        if self.device.battery_level is not None:
            attrs[ATTR_BATTERY_LEVEL] = self.device.battery_level
        if self.device.holiday_active is not None:
            attrs[ATTR_STATE_HOLIDAY_MODE] = self.device.holiday_active
        if self.device.summer_active is not None:
            attrs[ATTR_STATE_SUMMER_MODE] = self.device.summer_active
        if ATTR_STATE_WINDOW_OPEN is not None:
            attrs[ATTR_STATE_WINDOW_OPEN] = self.device.window_open

        return attrs
