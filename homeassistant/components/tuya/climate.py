"""Support for the Tuya climate devices."""
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
    PRECISION_WHOLE,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import TuyaDevice
from .const import DOMAIN, TUYA_DATA, TUYA_DISCOVERY_NEW

DEVICE_TYPE = "climate"

PARALLEL_UPDATES = 0

HA_STATE_TO_TUYA = {
    HVAC_MODE_AUTO: "auto",
    HVAC_MODE_COOL: "cold",
    HVAC_MODE_FAN_ONLY: "wind",
    HVAC_MODE_HEAT: "hot",
}

TUYA_STATE_TO_HA = {value: key for key, value in HA_STATE_TO_TUYA.items()}

FAN_MODES = {FAN_LOW, FAN_MEDIUM, FAN_HIGH}


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

    async def async_added_to_hass(self):
        """Create operation list when add to hass."""
        await super().async_added_to_hass()
        modes = self._tuya.operation_list()
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
        unit = self._tuya.temperature_unit()
        if unit == "FAHRENHEIT":
            return TEMP_FAHRENHEIT
        return TEMP_CELSIUS

    @property
    def hvac_mode(self):
        """Return current operation ie. heat, cool, idle."""
        if not self._tuya.state():
            return HVAC_MODE_OFF

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

        if not self._tuya.state():
            self._tuya.turn_on()

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
        return self._tuya.min_temp()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._tuya.max_temp()
