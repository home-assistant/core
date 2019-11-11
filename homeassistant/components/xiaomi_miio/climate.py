"""Support for Xiaomi Mi Air Dehumidifier."""
import asyncio
import logging
from enum import Enum
from functools import partial

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.climate import (
    ClimateDevice,
    PLATFORM_SCHEMA,
    DOMAIN
)
from homeassistant.components.climate.const import (
    HVAC_MODE_DRY,
    HVAC_MODE_OFF,
    ATTR_HVAC_MODES,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    SUPPORT_TARGET_HUMIDITY,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE
)
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_TOKEN,
    ATTR_ENTITY_ID,
    TEMP_CELSIUS
)
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Miio Device'
DATA_KEY = 'fan.xiaomi_miio'

CONF_MODEL = 'model'
MODEL_AIRDEHUMIDIFIER_V1 = 'nwt.derh.wdh318efw1'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN):
            vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(
            [
                MODEL_AIRDEHUMIDIFIER_V1,
            ]
        ),
    }
)

ATTR_MODEL = 'model'

# Air Dehumidifier
ATTR_TEMPERATURE = 'temperature'
ATTR_MODE = 'mode'
ATTR_BUZZER = 'buzzer'
ATTR_CHILD_LOCK = 'child_lock'
ATTR_LED = 'led'
ATTR_FAN_SPEED = 'fan_speed'
ATTR_TARGET_HUMIDITY = 'target_humidity'
ATTR_TANK_FULL = 'tank_full'
ATTR_COMPRESSOR_STATUS = 'compressor_status'
ATTR_DEFROST_STATUS = 'defrost_status'
ATTR_FAN_ST = 'fan_st'
ATTR_ALARM = 'alarm'

# Map attributes to properties of the state object
AVAILABLE_ATTRIBUTES_AIRDEHUMIDIFIER = {
    ATTR_TEMPERATURE: 'temperature',
    ATTR_HUMIDITY: 'humidity',
    ATTR_MODE: 'mode',
    ATTR_BUZZER: 'buzzer',
    ATTR_CHILD_LOCK: 'child_lock',
    ATTR_TARGET_HUMIDITY: 'target_humidity',
    ATTR_LED: 'led',
    ATTR_FAN_SPEED: 'fan_speed',
    ATTR_TANK_FULL: 'tank_full',
    ATTR_COMPRESSOR_STATUS: 'compressor_status',
    ATTR_DEFROST_STATUS: 'defrost_status',
    ATTR_FAN_ST: 'fan_st',
    ATTR_ALARM: 'alarm',
}

SUCCESS = ['ok']

FEATURE_SET_BUZZER = 1
FEATURE_SET_LED = 2
FEATURE_SET_CHILD_LOCK = 4
FEATURE_SET_TARGET_HUMIDITY = 8

FEATURE_FLAGS_AIRDEHUMIDIFIER = (
        FEATURE_SET_BUZZER
        | FEATURE_SET_CHILD_LOCK
        | FEATURE_SET_LED
        | FEATURE_SET_TARGET_HUMIDITY
)

SERVICE_SET_BUZZER_ON = 'xiaomi_miio_set_buzzer_on'
SERVICE_SET_BUZZER_OFF = 'xiaomi_miio_set_buzzer_off'
SERVICE_SET_LED_ON = 'xiaomi_miio_set_led_on'
SERVICE_SET_LED_OFF = 'xiaomi_miio_set_led_off'
SERVICE_SET_CHILD_LOCK_ON = 'xiaomi_miio_set_child_lock_on'
SERVICE_SET_CHILD_LOCK_OFF = 'xiaomi_miio_set_child_lock_off'

AIRDEHUMIDIFIER_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
    }
)

SERVICE_TO_METHOD = {
    SERVICE_SET_BUZZER_ON: {"method": "async_set_buzzer_on"},
    SERVICE_SET_BUZZER_OFF: {"method": "async_set_buzzer_off"},
    SERVICE_SET_LED_ON: {"method": "async_set_led_on"},
    SERVICE_SET_LED_OFF: {"method": "async_set_led_off"},
    SERVICE_SET_CHILD_LOCK_ON: {"method": "async_set_child_lock_on"},
    SERVICE_SET_CHILD_LOCK_OFF: {"method": "async_set_child_lock_off"},
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the miio fan device from config."""
    from miio import Device, DeviceException
    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    model = config.get(CONF_MODEL)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])
    unique_id = None

    if model is None:
        try:
            miio_device = Device(host, token)
            device_info = miio_device.info()
            model = device_info.model
            unique_id = "{}-{}".format(model, device_info.mac_address)
            _LOGGER.info("%s %s %s detected",
                         model,
                         device_info.firmware_version,
                         device_info.hardware_version)
        except DeviceException:
            raise PlatformNotReady

    if model.startswith('nwt.derh.'):
        from miio import AirDehumidifier
        air_dehumidifier = AirDehumidifier(host, token, model=model)
        device = XiaomiAirDehumidifier(name, air_dehumidifier, model, unique_id)
    else:
        _LOGGER.error(
            'Unsupported device found! Please create an issue at '
            'https://github.com/rytilahti/python-miio/issues '
            'and provide the following data: %s', model)
        return False

    hass.data[DATA_KEY][host] = device
    async_add_entities([device], update_before_add=True)

    async def async_service_handler(service):
        """Map services to methods on XiaomiAirDehumidifier."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {
            key: value for key, value in service.data.items() if
            key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            devices = [
                device
                for device in hass.data[DATA_KEY].values()
                if device.entity_id in entity_ids
            ]
        else:
            devices = hass.data[DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method["method"]):
                continue
            await getattr(device, method["method"])(**params)
            update_tasks.append(device.async_update_ha_state(True))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for air_dehumidifier_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[air_dehumidifier_service].get(
            "schema", AIRDEHUMIDIFIER_SERVICE_SCHEMA
        )
        hass.services.async_register(
            DOMAIN, air_dehumidifier_service, async_service_handler,
            schema=schema
        )


class XiaomiGenericDevice(ClimateDevice):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the generic Xiaomi device."""
        self._name = name
        self._device = device
        self._model = model
        self._unique_id = unique_id

        self._available = False
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._model,
        }
        self._device_features = FEATURE_SET_CHILD_LOCK
        self._skip_update = False

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        from miio import DeviceException
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            self._available = False
            return False

    async def async_turn_on(self):
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.", self._device.on)

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self):
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off)

        if result:
            self._state = False
            self._skip_update = True

    async def async_set_buzzer_on(self):
        """Turn the buzzer on."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device on failed.",
            self._device.set_buzzer, True)

    async def async_set_buzzer_off(self):
        """Turn the buzzer off."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device off failed.",
            self._device.set_buzzer, False)

    async def async_set_child_lock_on(self):
        """Turn the child lock on."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device on failed.",
            self._device.set_child_lock, True)

    async def async_set_child_lock_off(self):
        """Turn the child lock off."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device off failed.",
            self._device.set_child_lock, False)


class XiaomiAirDehumidifier(XiaomiGenericDevice):
    """Representation of a Xiaomi Air Dehumidifier."""

    def __init__(self, name, device, model, unique_id):
        """Initialize the plug switch."""
        from miio.airdehumidifier import OperationMode, FanSpeed

        super().__init__(name, device, model, unique_id)

        self._device_features = FEATURE_FLAGS_AIRDEHUMIDIFIER
        self._available_attributes = AVAILABLE_ATTRIBUTES_AIRDEHUMIDIFIER
        self._preset_modes_list = [mode.name for mode in OperationMode]
        self._fan_mode_list = [mode.name for mode in FanSpeed if
                               mode not in [FanSpeed.Sleep, FanSpeed.Strong]]

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes})

    @property
    def state_attributes(self):
        """Return the optional state attributes."""
        supported_features = self.supported_features
        data = {
            ATTR_HVAC_MODES: self.hvac_modes,
        }

        if self.current_humidity is not None:
            data[ATTR_CURRENT_HUMIDITY] = self.current_humidity

        if supported_features & SUPPORT_TARGET_HUMIDITY:
            data[ATTR_HUMIDITY] = self.target_humidity
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        if supported_features & SUPPORT_FAN_MODE:
            data[ATTR_FAN_MODE] = self.fan_mode
            data[ATTR_FAN_MODES] = self.fan_modes

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode
            data[ATTR_PRESET_MODES] = self.preset_modes

        return data

    @property
    def supported_features(self):
        """Flag supported features."""
        if self.hvac_mode == HVAC_MODE_OFF:
            return 0

        from miio.airdehumidifier import OperationMode

        features = SUPPORT_PRESET_MODE
        mode = OperationMode(self._state_attrs[ATTR_MODE])
        if mode == OperationMode.Auto:
            features |= SUPPORT_TARGET_HUMIDITY
        if mode != OperationMode.DryCloth:
            features |= SUPPORT_FAN_MODE
        return features

    async def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException

        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._state_attrs.update(
                {key: self._extract_value_from_attribute(state, value) for
                 key, value in self._available_attributes.items()})
            self._state_attrs[ATTR_TEMPERATURE] = None
            self._state_attrs[ATTR_HUMIDITY] = \
                self._state_attrs[ATTR_TARGET_HUMIDITY]
        except DeviceException as ex:
            self._available = False
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._state_attrs[ATTR_HUMIDITY]

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._state_attrs[ATTR_TARGET_HUMIDITY]

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return 40

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return 60

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.is_on:
            return HVAC_MODE_DRY
        return HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_OFF, HVAC_MODE_DRY]

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return self._preset_modes_list

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        from miio.airdehumidifier import OperationMode

        return OperationMode(self._state_attrs[ATTR_MODE]).name

    @property
    def fan_mode(self):
        """Return the fan setting."""
        from miio.airdehumidifier import OperationMode, FanSpeed

        if self.preset_mode == OperationMode.DryCloth.name:
            return None
        return FanSpeed(self._state_attrs[ATTR_FAN_ST]).name

    @property
    def fan_modes(self):
        """Return the list of available fan modes."""
        return self._fan_mode_list

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_DRY:
            await self.async_turn_on()
        elif hvac_mode == HVAC_MODE_OFF:
            await self.async_turn_off()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        from miio.airdehumidifier import OperationMode

        await self._try_command(
            "Setting the fan mode of the miio device failed.",
            self._device.set_mode, OperationMode[preset_mode])

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        from miio.airdehumidifier import OperationMode

        if self.preset_mode != OperationMode.Auto.name:
            await self.async_set_preset_mode(OperationMode.Auto)

        humidity = round(humidity / 10) * 10
        await self._try_command(
            "Setting the humidity of the miio device failed.",
            self._device.set_target_humidity, humidity)

    async def async_set_fan_mode(self, fan_mode: str):
        """Set new target fan mode."""
        from miio.airdehumidifier import OperationMode, FanSpeed

        if self.preset_mode != OperationMode.DryCloth.name:
            await self._try_command(
                "Setting the fan mode of the miio device failed.",
                self._device.set_fan_speed, FanSpeed[fan_mode])
