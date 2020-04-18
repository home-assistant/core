"""Support for the Tuya climate devices."""
from homeassistant.components.climate import ENTITY_ID_FORMAT, ClimateDevice
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
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

from . import DATA_TUYA, TuyaDevice

DEVICE_TYPE = "climate"

HA_STATE_TO_TUYA = {
    HVAC_MODE_AUTO: "auto",
    HVAC_MODE_COOL: "cold",
    HVAC_MODE_FAN_ONLY: "wind",
    HVAC_MODE_HEAT: "hot",
}

TUYA_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_TUYA.items()}

FAN_MODES = {FAN_LOW, FAN_MEDIUM, FAN_HIGH}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Tuya Climate devices."""
    if discovery_info is None:
        return
    tuya = hass.data[DATA_TUYA]
    dev_ids = discovery_info.get("dev_ids")
    devices = []
    for dev_id in dev_ids:
        device = tuya.get_device_by_id(dev_id)
        if device is None:
            continue
        devices.append(TuyaClimateDevice(device))
    add_entities(devices)


class TuyaClimateDevice(TuyaDevice, ClimateDevice):
    """Tuya climate devices,include air conditioner,heater."""

    def __init__(self, tuya):
        """Init climate device."""
        super().__init__(tuya)
        self.entity_id = ENTITY_ID_FORMAT.format(tuya.object_id())
        self.operations = [HVAC_MODE_OFF]

    async def async_added_to_hass(self):
        """Create operation list when add to hass."""
        await super().async_added_to_hass()
        modes = self.tuya.operation_list()
        if modes is None:
            return

        for mode in modes:
            if mode in TUYA_STATE_TO_HA:
                self.operations.append(TUYA_STATE_TO_HA[mode])

    @property
    def precision(self):
        """Return the precision of the system."""
        return PRECISION_WHOLE

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        unit = self.tuya.temperature_unit()
        if unit == "FAHRENHEIT":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if not self.tuya.state():
            return HVAC_MODE_OFF

        mode = self.tuya.current_operation()
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
        return self.tuya.current_temperature()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.tuya.target_temperature()

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return self.tuya.target_temperature_step()

    @property
    def fan_mode(self):
        """Return the fan setting."""
        return self.tuya.current_fan_mode()

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self.tuya.fan_list()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            self.tuya.set_temperature(kwargs[ATTR_TEMPERATURE])

    def set_fan_mode(self, fan_mode):
        """Set new target fan mode."""
        self.tuya.set_fan_mode(fan_mode)

    def set_hvac_mode(self, hvac_mode):
        """Set new target operation mode."""
        if hvac_mode == HVAC_MODE_OFF:
            self.tuya.turn_off()

        if not self.tuya.state():
            self.tuya.turn_on()

        self.tuya.set_operation_mode(HA_STATE_TO_TUYA.get(hvac_mode))

    @property
    def supported_features(self):
        """Return the list of supported features."""
        supports = 0
        if self.tuya.support_target_temperature():
            supports = supports | SUPPORT_TARGET_TEMPERATURE
        if self.tuya.support_wind_speed():
            supports = supports | SUPPORT_FAN_MODE
        return supports

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self.tuya.min_temp()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self.tuya.max_temp()
