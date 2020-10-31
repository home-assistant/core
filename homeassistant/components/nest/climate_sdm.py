"""Support for Google Nest SDM climate devices."""

from typing import Optional

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import TemperatureTrait
from google_nest_sdm.thermostat_traits import (
    ThermostatEcoTrait,
    ThermostatHvacTrait,
    ThermostatModeTrait,
    ThermostatTemperatureSetpointTrait,
)

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, SIGNAL_NEST_UPDATE
from .device_info import DeviceInfo

# Mapping for sdm.devices.traits.ThermostatMode mode field
THERMOSTAT_MODE_MAP = {
    "OFF": HVAC_MODE_OFF,
    "HEAT": HVAC_MODE_HEAT,
    "COOL": HVAC_MODE_COOL,
    "HEATCOOL": HVAC_MODE_HEAT_COOL,
}
THERMOSTAT_INV_MODE_MAP = {v: k for k, v in THERMOSTAT_MODE_MAP.items()}

# Mode for sdm.devices.traits.ThermostatEco
THERMOSTAT_ECO_MODE = "MANUAL_ECO"

# Mapping for sdm.devices.traits.ThermostatHvac status field
THERMOSTAT_HVAC_STATUS_MAP = {
    "OFF": CURRENT_HVAC_OFF,
    "HEATING": CURRENT_HVAC_HEAT,
    "COOLING": CURRENT_HVAC_COOL,
}

# Mapping to determine the trait that supports the target temperatures
# based on the current HVAC mode
THERMOSTAT_SETPOINT_TRAIT_MAP = {
    HVAC_MODE_COOL: ThermostatTemperatureSetpointTrait.NAME,
    HVAC_MODE_HEAT: ThermostatTemperatureSetpointTrait.NAME,
    HVAC_MODE_HEAT_COOL: ThermostatTemperatureSetpointTrait.NAME,
    HVAC_MODE_AUTO: ThermostatEcoTrait.NAME,
}
THERMOSTAT_TARGET_LOW_MODES = [HVAC_MODE_HEAT, HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]
THERMOSTAT_TARGET_HIGH_MODES = [HVAC_MODE_COOL, HVAC_MODE_HEAT_COOL, HVAC_MODE_AUTO]


async def async_setup_sdm_entry(
    hass: HomeAssistantType, entry: ConfigEntry, async_add_entities
) -> None:
    """Set up the sensors."""

    subscriber = hass.data[DOMAIN][entry.entry_id]
    device_manager = await subscriber.async_get_device_manager()

    # Fetch initial data so we have data when entities subscribe.

    entities = []
    for device in device_manager.devices.values():
        if ThermostatHvacTrait.NAME in device.traits:
            entities.append(ThermostatEntity(device))
    async_add_entities(entities)


class ThermostatEntity(ClimateEntity):
    """A nest thermostat climate entity."""

    def __init__(self, device: Device):
        """Initialize ThermostatEntity."""
        self._device = device
        self._device_info = DeviceInfo(device)

    @property
    def should_poll(self) -> bool:
        """Disable polling since entities have state pushed via pubsub."""
        return False

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        # The API "name" field is a unique device identifier.
        return self._device.name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._device_info.device_name
        return self.device_name

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device_info.device_info

    async def async_added_to_hass(self):
        """Run when entity is added to register update signal handler."""
        # Event messages trigger the SIGNAL_NEST_UPDATE, which is intercepted
        # here to re-fresh the signals from _device.  Unregister this callback
        # when the entity is removed.
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_NEST_UPDATE,
                self.async_write_ha_state,
            )
        )

    @property
    def temperature_unit(self):
        """Return the unit of temperature measurement for the system."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if TemperatureTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[TemperatureTrait.NAME]
        return trait.ambient_temperature_celsius

    @property
    def target_temperature(self):
        """Return the temperature currently set to be reached."""
        if not self.target_temperature_high and not self.target_temperature_low:
            return None
        # If there is both a high and low temperature set, then we must be
        # in HEAT_COOL or AUTO/ECO mode.  Infer the target temperature based on
        # whether the unit is currently heating or cooling.
        if self.target_temperature_high and self.target_temperature_low:
            if self.hvac_action == CURRENT_HVAC_HEAT:
                return self.target_temperature_low
            elif self.hvac_action == CURRENT_HVAC_COOL:
                return self.target_temperature_low
        if self.target_temperature_high:
            return self.target_temperature_high
        else:
            return self.target_temperature_low

    @property
    def target_temperature_high(self):
        """Return the upper bound target temperature."""
        if self.hvac_mode not in THERMOSTAT_TARGET_HIGH_MODES:
            return None
        trait = self._target_temperature_trait
        if not trait:
            return None
        return trait.cool_celsius

    @property
    def target_temperature_low(self):
        """Return the lower bound target temperature."""
        if self.hvac_mode not in THERMOSTAT_TARGET_LOW_MODES:
            return None
        trait = self._target_temperature_trait
        if not trait:
            return None
        return trait.heat_celsius

    @property
    def _target_temperature_trait(self):
        """Return the correct trait with a target temp depending on mode."""
        if not self.hvac_mode:
            return None
        if self.hvac_mode not in THERMOSTAT_SETPOINT_TRAIT_MAP:
            return None
        trait_name = THERMOSTAT_SETPOINT_TRAIT_MAP[self.hvac_mode]
        if trait_name not in self._device.traits:
            return None
        return self._device.traits[trait_name]

    @property
    def hvac_mode(self):
        """Return the current operation (e.g. heat, cool, idle)."""
        if ThermostatEcoTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatEcoTrait.NAME]
            if trait.mode == THERMOSTAT_ECO_MODE:
                return HVAC_MODE_AUTO
        if ThermostatModeTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatModeTrait.NAME]
            if trait.mode in THERMOSTAT_MODE_MAP:
                return THERMOSTAT_MODE_MAP[trait.mode]
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        supported_modes = []
        if ThermostatEcoTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatEcoTrait.NAME]
        if ThermostatModeTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatModeTrait.NAME]
            for mode in trait.available_modes:
                if mode in THERMOSTAT_MODE_MAP:
                    supported_modes.append(THERMOSTAT_MODE_MAP[mode])
        return supported_modes

    @property
    def hvac_action(self):
        """Return the current HVAC action (heating, cooling)."""
        if ThermostatHvacTrait.NAME not in self._device.traits:
            return None
        trait = self._device.traits[ThermostatHvacTrait.NAME]
        if trait.status in THERMOSTAT_HVAC_STATUS_MAP:
            return THERMOSTAT_HVAC_STATUS_MAP[trait.status]
        return None

    @property
    def preset_mode(self):
        """Return the current active preset."""
        if ThermostatEcoTrait.NAME in self._device.traits:
            trait = self._device.traits[ThermostatEcoTrait.NAME]
            if trait.mode == "MANUAL_ECO":
                return PRESET_ECO
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return the available presets."""
        modes = []
        if ThermostatEcoTrait.NAME in self._device.traits:
            modes.append(PRESET_ECO)
        return modes

    @property
    def supported_features(self):
        """Bitmap of supported features."""
        features = 0
        if ThermostatTemperatureSetpointTrait.NAME in self._device.traits:
            features = (
                features | SUPPORT_TARGET_TEMPERATURE | SUPPORT_TARGET_TEMPERATURE_RANGE
            )
        if ThermostatEcoTrait.NAME in self._device.traits:
            features = features | SUPPORT_PRESET_MODE
        return features

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            return
        if hvac_mode not in THERMOSTAT_INV_MODE_MAP:
            return
        api_mode = THERMOSTAT_INV_MODE_MAP[hvac_mode]
        if ThermostatModeTrait.NAME not in self._device.traits:
            return
        trait = self._device.traits[ThermostatModeTrait.NAME]
        await trait.set_mode(api_mode)

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        low_temp = kwargs.get(ATTR_TARGET_TEMP_LOW)
        high_temp = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        temp = kwargs.get(ATTR_TEMPERATURE)
        if ThermostatTemperatureSetpointTrait.NAME not in self._device.traits:
            return
        trait = self._device.traits[ThermostatTemperatureSetpointTrait.NAME]
        if self.preset_mode == PRESET_ECO or self.hvac_mode == HVAC_MODE_HEAT_COOL:
            if low_temp and high_temp:
                return await trait.set_range(low_temp, high_temp)
        elif self.hvac_mode == HVAC_MODE_COOL and temp:
            return await trait.set_cool(temp)
        elif self.hvac_mode == HVAC_MODE_HEAT and temp:
            return await trait.set_heat(temp)

    async def async_set_preset_mode(self, preset_mode):
        """Set new target preset mode."""
        if preset_mode not in [PRESET_ECO, PRESET_NONE]:
            return
        if ThermostatEcoTrait.NAME not in self._device.traits:
            return
        trait = self._device.traits[ThermostatEcoTrait.NAME]
        if preset_mode == PRESET_ECO:
            await trait.set_mode("MANUAL_ECO")
        elif preset_mode == PRESET_NONE:
            await trait.set_mode("OFF")
