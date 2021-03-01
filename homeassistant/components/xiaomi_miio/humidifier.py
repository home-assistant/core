"""Support for Xiaomi Mi Air Humidifier."""
import asyncio
from enum import Enum
from functools import partial
import logging

from miio import (  # pylint: disable=import-error
    AirHumidifier,
    AirHumidifierMiot,
    DeviceException,
)
from miio.airhumidifier import (  # pylint: disable=import-error, import-error
    LedBrightness as AirhumidifierLedBrightness,
    OperationMode as AirhumidifierOperationMode,
)
from miio.airhumidifier_miot import (  # pylint: disable=import-error, import-error
    LedBrightness as AirhumidifierMiotLedBrightness,
    OperationMode as AirhumidifierMiotOperationMode,
    PressedButton as AirhumidifierPressedButton,
)
import voluptuous as vol

from homeassistant.components.humidifier import PLATFORM_SCHEMA, HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEVICE_CLASS_HUMIDIFIER,
    SUPPORT_MODES,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    MODEL_AIRHUMIDIFIER_CA1,
    MODEL_AIRHUMIDIFIER_CA4,
    MODEL_AIRHUMIDIFIER_CB1,
    MODELS_HUMIDIFIER,
    MODELS_HUMIDIFIER_MIOT,
    SERVICE_HUMIDIFIER_SET_BUZZER_OFF,
    SERVICE_HUMIDIFIER_SET_BUZZER_ON,
    SERVICE_HUMIDIFIER_SET_CHILD_LOCK_OFF,
    SERVICE_HUMIDIFIER_SET_CHILD_LOCK_ON,
    SERVICE_HUMIDIFIER_SET_DRY_OFF,
    SERVICE_HUMIDIFIER_SET_DRY_ON,
    SERVICE_HUMIDIFIER_SET_LED_BRIGHTNESS,
    SERVICE_HUMIDIFIER_SET_LED_OFF,
    SERVICE_HUMIDIFIER_SET_LED_ON,
    SERVICE_HUMIDIFIER_SET_TARGET_HUMIDITY,
)
from .device import XiaomiMiioEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 80
DATA_KEY = "humidifier.xiaomi_miio"

CONF_MODEL = "model"

ATTR_MODEL = "model"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(MODELS_HUMIDIFIER),
    }
)

ATTR_TEMPERATURE = "temperature"
ATTR_HUMIDITY = "humidity"
ATTR_BUZZER = "buzzer"
ATTR_CHILD_LOCK = "child_lock"
ATTR_LED = "led"
ATTR_LED_BRIGHTNESS = "led_brightness"
ATTR_BRIGHTNESS = "brightness"
ATTR_LEVEL = "level"
ATTR_CURRENT_HUMIDITY = "current_humidity"
ATTR_FEATURES = "features"
ATTR_VOLUME = "volume"
ATTR_USE_TIME = "use_time"
ATTR_BUTTON_PRESSED = "button_pressed"

# Air Humidifier
ATTR_TARGET_HUMIDITY = "target_humidity"
ATTR_TRANS_LEVEL = "trans_level"
ATTR_HARDWARE_VERSION = "hardware_version"

# Air Humidifier CA
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_DEPTH = "depth"
ATTR_DRY = "dry"

# Air Humidifier CA4
ATTR_ACTUAL_MOTOR_SPEED = "actual_speed"
ATTR_FAHRENHEIT = "fahrenheit"
ATTR_FAULT = "fault"

MODE_HIGH = "high"
MODE_LOW = "low"
MODE_MEDIUM = "medium"

AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_COMMON = {
    ATTR_TEMPERATURE: "temperature",
    ATTR_CURRENT_HUMIDITY: "humidity",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_LED_BRIGHTNESS: "led_brightness",
    ATTR_USE_TIME: "use_time",
}

AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER = {
    **AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_COMMON,
    ATTR_TRANS_LEVEL: "trans_level",
    ATTR_BUTTON_PRESSED: "button_pressed",
    ATTR_HARDWARE_VERSION: "hardware_version",
}

AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_CA_AND_CB = {
    **AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_COMMON,
    ATTR_MOTOR_SPEED: "motor_speed",
    ATTR_DEPTH: "depth",
    ATTR_DRY: "dry",
    ATTR_HARDWARE_VERSION: "hardware_version",
}

AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_CA4 = {
    **AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_COMMON,
    ATTR_ACTUAL_MOTOR_SPEED: "actual_speed",
    ATTR_BUTTON_PRESSED: "button_pressed",
    ATTR_DRY: "dry",
    ATTR_FAHRENHEIT: "fahrenheit",
    ATTR_MOTOR_SPEED: "motor_speed",
}


OPERATION_MODES_HUMIDIFIER = ["Auto", "Silent", "Medium", "High"]

SUCCESS = ["ok"]

FEATURE_SET_MODE = 1
FEATURE_SET_BUZZER = 2
FEATURE_SET_LED = 4
FEATURE_SET_CHILD_LOCK = 8
FEATURE_SET_LED_BRIGHTNESS = 16
FEATURE_SET_TARGET_HUMIDITY = 32
FEATURE_SET_DRY = 64
FEATURE_SET_FAN_LEVEL = 128
FEATURE_SET_MOTOR_SPEED = 256

FEATURE_FLAGS_AIRHUMIDIFIER = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_TARGET_HUMIDITY
)

FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB = FEATURE_FLAGS_AIRHUMIDIFIER | FEATURE_SET_DRY

FEATURE_FLAGS_AIRHUMIDIFIER_CA4 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_TARGET_HUMIDITY
    | FEATURE_SET_DRY
    | FEATURE_SET_MOTOR_SPEED
)

HUMIDIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_LED_BRIGHTNESS = HUMIDIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=2))}
)

SERVICE_SCHEMA_VOLUME = HUMIDIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_VOLUME): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100))}
)

SERVICE_SCHEMA_TARGET_HUMIDITY = HUMIDIFIER_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_HUMIDITY): vol.All(
            vol.Coerce(int), vol.In([30, 40, 50, 60, 70, 80])
        )
    }
)

SERVICE_TO_METHOD = {
    SERVICE_HUMIDIFIER_SET_BUZZER_ON: {"method": "async_set_buzzer_on"},
    SERVICE_HUMIDIFIER_SET_BUZZER_OFF: {"method": "async_set_buzzer_off"},
    SERVICE_HUMIDIFIER_SET_LED_ON: {"method": "async_set_led_on"},
    SERVICE_HUMIDIFIER_SET_LED_OFF: {"method": "async_set_led_off"},
    SERVICE_HUMIDIFIER_SET_CHILD_LOCK_ON: {"method": "async_set_child_lock_on"},
    SERVICE_HUMIDIFIER_SET_CHILD_LOCK_OFF: {"method": "async_set_child_lock_off"},
    SERVICE_HUMIDIFIER_SET_LED_BRIGHTNESS: {
        "method": "async_set_led_brightness",
        "schema": SERVICE_SCHEMA_LED_BRIGHTNESS,
    },
    SERVICE_HUMIDIFIER_SET_TARGET_HUMIDITY: {
        "method": "async_set_humidity",
        "schema": SERVICE_SCHEMA_TARGET_HUMIDITY,
    },
    SERVICE_HUMIDIFIER_SET_DRY_ON: {"method": "async_set_dry_on"},
    SERVICE_HUMIDIFIER_SET_DRY_OFF: {"method": "async_set_dry_off"},
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fan from a config entry."""
    entities = []

    if config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        if DATA_KEY not in hass.data:
            hass.data[DATA_KEY] = {}

        host = config_entry.data[CONF_HOST]
        token = config_entry.data[CONF_TOKEN]
        name = config_entry.title
        model = config_entry.data[CONF_MODEL]
        unique_id = config_entry.unique_id

        _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

        if model in MODELS_HUMIDIFIER_MIOT:
            air_humidifier = AirHumidifierMiot(host, token)
            entity = XiaomiAirHumidifierMiot(
                name, air_humidifier, config_entry, unique_id
            )
        elif model in MODELS_HUMIDIFIER:
            air_humidifier = AirHumidifier(host, token, model=model)
            entity = XiaomiAirHumidifier(name, air_humidifier, config_entry, unique_id)
        else:
            _LOGGER.error(
                "Unsupported device found! Please create an issue at "
                "https://github.com/syssi/xiaomi_airpurifier/issues "
                "and provide the following data: %s",
                model,
            )
            return

        hass.data[DATA_KEY][host] = entity
        entities.append(entity)

        async def async_service_handler(service):
            """Map services to methods on XiaomiAirPurifier."""
            method = SERVICE_TO_METHOD[service.service]
            params = {
                key: value
                for key, value in service.data.items()
                if key != ATTR_ENTITY_ID
            }
            entity_ids = service.data.get(ATTR_ENTITY_ID)
            if entity_ids:
                entities = [
                    entity
                    for entity in hass.data[DATA_KEY].values()
                    if entity.entity_id in entity_ids
                ]
            else:
                entities = hass.data[DATA_KEY].values()

            update_tasks = []

            for entity in entities:
                entity_method = getattr(entity, method["method"], None)
                if not entity_method:
                    continue
                await entity_method(**params)
                update_tasks.append(
                    hass.async_create_task(entity.async_update_ha_state(True))
                )

            if update_tasks:
                await asyncio.wait(update_tasks)

        for air_purifier_service in SERVICE_TO_METHOD:
            schema = SERVICE_TO_METHOD[air_purifier_service].get(
                "schema", HUMIDIFIER_SERVICE_SCHEMA
            )
            hass.services.async_register(
                DOMAIN, air_purifier_service, async_service_handler, schema=schema
            )

    async_add_entities(entities, update_before_add=True)


class XiaomiGenericDevice(XiaomiMiioEntity, HumidifierEntity):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id)

        self._available = False
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}
        self._device_features = FEATURE_SET_CHILD_LOCK
        self._skip_update = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MODES

    @property
    def should_poll(self):
        """Poll the device."""
        return True

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

    @property
    def device_class(self):
        """Return the device class of the humidifier."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    async def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a miio device command handling error messages."""
        try:
            result = await self.hass.async_add_executor_job(
                partial(func, *args, **kwargs)
            )

            _LOGGER.debug("Response received from miio device: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            if self._available:
                _LOGGER.error(mask_error, exc)
                self._available = False

            return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the device on."""

        result = await self._try_command(
            "Turning the miio device on failed.", self._device.on
        )

        if result:
            self._state = True
            self._skip_update = True

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )

        if result:
            self._state = False
            self._skip_update = True

    async def async_set_buzzer_on(self):
        """Turn the buzzer on."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device on failed.",
            self._device.set_buzzer,
            True,
        )

    async def async_set_buzzer_off(self):
        """Turn the buzzer off."""
        if self._device_features & FEATURE_SET_BUZZER == 0:
            return

        await self._try_command(
            "Turning the buzzer of the miio device off failed.",
            self._device.set_buzzer,
            False,
        )

    async def async_set_child_lock_on(self):
        """Turn the child lock on."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device on failed.",
            self._device.set_child_lock,
            True,
        )

    async def async_set_child_lock_off(self):
        """Turn the child lock off."""
        if self._device_features & FEATURE_SET_CHILD_LOCK == 0:
            return

        await self._try_command(
            "Turning the child lock of the miio device off failed.",
            self._device.set_child_lock,
            False,
        )


class XiaomiAirHumidifier(XiaomiGenericDevice):
    """Representation of a Xiaomi Air Humidifier."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id)
        self._mode = None
        self._target_humidity = None

        if self._model in [MODEL_AIRHUMIDIFIER_CA1, MODEL_AIRHUMIDIFIER_CB1]:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA_AND_CB
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_CA_AND_CB
            self._available_modes = [
                mode.name
                for mode in AirhumidifierOperationMode
                if mode is not AirhumidifierOperationMode.Strong
            ]
        elif self._model in [MODEL_AIRHUMIDIFIER_CA4]:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER_CA4
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER_CA4
            self._available_modes = [MODE_LOW, MODE_MEDIUM, MODE_HIGH]
        else:
            self._device_features = FEATURE_FLAGS_AIRHUMIDIFIER
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRHUMIDIFIER
            self._available_modes = [mode.name for mode in AirhumidifierOperationMode]

        self._state_attrs.update(
            {attribute: None for attribute in self._available_attributes}
        )

    async def async_update(self):
        """Fetch state from the device."""
        # On state change the device doesn't provide the new state immediately.
        if self._skip_update:
            self._skip_update = False
            return

        try:
            state = await self.hass.async_add_executor_job(self._device.status)
            _LOGGER.debug("Got new state: %s", state)

            self._available = True
            self._state = state.is_on
            self._mode = state.mode.name
            self._target_humidity = state.target_humidity
            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )

        except DeviceException as ex:
            if self._available:
                self._available = False
                _LOGGER.error("Got exception while fetching the state: %s", ex)

    @property
    def available_modes(self) -> list:
        """Get the list of available modes."""
        return self._available_modes

    @property
    def mode(self):
        """Return the current mode."""
        return self._mode

    async def async_set_mode(self, mode: str) -> None:
        """Set the speed of the fan."""
        if self._device_features & FEATURE_SET_MODE == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", mode)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirhumidifierOperationMode[mode.title()],
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierLedBrightness(brightness),
        )

    async def async_set_humidity(self, humidity: int = 40):
        """Set the target humidity."""
        if self._device_features & FEATURE_SET_TARGET_HUMIDITY == 0:
            return

        # Allowed target humidity values are 30, 40, 50, 60, 70, 80 percent
        await self._try_command(
            "Setting the target humidity of the miio device failed.",
            self._device.set_target_humidity,
            round(humidity, -1),
        )

    async def async_set_dry_on(self):
        """Turn the dry mode on."""
        if self._device_features & FEATURE_SET_DRY == 0:
            return

        await self._try_command(
            "Turning the dry mode of the miio device off failed.",
            self._device.set_dry,
            True,
        )

    async def async_set_dry_off(self):
        """Turn the dry mode off."""
        if self._device_features & FEATURE_SET_DRY == 0:
            return

        await self._try_command(
            "Turning the dry mode of the miio device off failed.",
            self._device.set_dry,
            False,
        )


class XiaomiAirHumidifierMiot(XiaomiAirHumidifier):
    """Representation of a Xiaomi Air Humidifier (MiOT protocol)."""

    MODE_MAPPING = {
        AirhumidifierMiotOperationMode.Low: MODE_LOW,
        AirhumidifierMiotOperationMode.Mid: MODE_MEDIUM,
        AirhumidifierMiotOperationMode.High: MODE_HIGH,
    }

    REVERSE_MODE_MAPPING = {v: k for k, v in MODE_MAPPING.items()}

    @property
    def mode(self):
        """Return the current mode."""
        if self._state:
            return self.MODE_MAPPING.get(
                AirhumidifierMiotOperationMode(self._state_attrs[ATTR_MODE])
            )

        return None

    @property
    def button_pressed(self):
        """Return the last button pressed."""
        if self._state:
            return AirhumidifierPressedButton(
                self._state_attrs[ATTR_BUTTON_PRESSED]
            ).name

        return None

    async def async_set_mode(self, mode: str) -> None:
        """Set the mode of the fan."""
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.REVERSE_MODE_MAPPING[mode],
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirhumidifierMiotLedBrightness(brightness),
        )

    async def async_set_motor_speed(self, motor_speed: int = 400):
        """Set the target motor speed."""
        if self._device_features & FEATURE_SET_MOTOR_SPEED == 0:
            return

        await self._try_command(
            "Setting the target motor speed of the miio device failed.",
            self._device.set_speed,
            motor_speed,
        )
