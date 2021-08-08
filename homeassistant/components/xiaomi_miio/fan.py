"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier."""
import asyncio
from enum import Enum
from functools import partial
import logging
import math

from miio import AirFresh, AirPurifier, AirPurifierMiot, DeviceException
from miio.airfresh import (
    LedBrightness as AirfreshLedBrightness,
    OperationMode as AirfreshOperationMode,
)
from miio.airpurifier import (
    LedBrightness as AirpurifierLedBrightness,
    OperationMode as AirpurifierOperationMode,
)
from miio.airpurifier_miot import (
    LedBrightness as AirpurifierMiotLedBrightness,
    OperationMode as AirpurifierMiotOperationMode,
)
import voluptuous as vol

from homeassistant.components.fan import (
    PLATFORM_SCHEMA,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    FEATURE_RESET_FILTER,
    FEATURE_SET_AUTO_DETECT,
    FEATURE_SET_BUZZER,
    FEATURE_SET_CHILD_LOCK,
    FEATURE_SET_EXTRA_FEATURES,
    FEATURE_SET_FAN_LEVEL,
    FEATURE_SET_FAVORITE_LEVEL,
    FEATURE_SET_LEARN_MODE,
    FEATURE_SET_LED,
    FEATURE_SET_LED_BRIGHTNESS,
    FEATURE_SET_VOLUME,
    MODEL_AIRPURIFIER_2H,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V3,
    MODELS_FAN,
    MODELS_PURIFIER_MIOT,
    SERVICE_RESET_FILTER,
    SERVICE_SET_AUTO_DETECT_OFF,
    SERVICE_SET_AUTO_DETECT_ON,
    SERVICE_SET_BUZZER_OFF,
    SERVICE_SET_BUZZER_ON,
    SERVICE_SET_CHILD_LOCK_OFF,
    SERVICE_SET_CHILD_LOCK_ON,
    SERVICE_SET_EXTRA_FEATURES,
    SERVICE_SET_FAN_LED_OFF,
    SERVICE_SET_FAN_LED_ON,
    SERVICE_SET_FAN_LEVEL,
    SERVICE_SET_FAVORITE_LEVEL,
    SERVICE_SET_LEARN_MODE_OFF,
    SERVICE_SET_LEARN_MODE_ON,
    SERVICE_SET_LED_BRIGHTNESS,
    SERVICE_SET_VOLUME,
    SUCCESS,
)
from .device import XiaomiMiioEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Xiaomi Miio Device"
DATA_KEY = "fan.xiaomi_miio"

CONF_MODEL = "model"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL): vol.In(MODELS_FAN),
    }
)

ATTR_MODEL = "model"

# Air Purifier
ATTR_HUMIDITY = "humidity"
ATTR_AIR_QUALITY_INDEX = "aqi"
ATTR_FILTER_HOURS_USED = "filter_hours_used"
ATTR_FILTER_LIFE = "filter_life_remaining"
ATTR_FAVORITE_LEVEL = "favorite_level"
ATTR_BUZZER = "buzzer"
ATTR_CHILD_LOCK = "child_lock"
ATTR_LED = "led"
ATTR_LED_BRIGHTNESS = "led_brightness"
ATTR_MOTOR_SPEED = "motor_speed"
ATTR_AVERAGE_AIR_QUALITY_INDEX = "average_aqi"
ATTR_PURIFY_VOLUME = "purify_volume"
ATTR_BRIGHTNESS = "brightness"
ATTR_LEVEL = "level"
ATTR_FAN_LEVEL = "fan_level"
ATTR_MOTOR2_SPEED = "motor2_speed"
ATTR_ILLUMINANCE = "illuminance"
ATTR_FILTER_RFID_PRODUCT_ID = "filter_rfid_product_id"
ATTR_FILTER_RFID_TAG = "filter_rfid_tag"
ATTR_FILTER_TYPE = "filter_type"
ATTR_LEARN_MODE = "learn_mode"
ATTR_SLEEP_TIME = "sleep_time"
ATTR_SLEEP_LEARN_COUNT = "sleep_mode_learn_count"
ATTR_EXTRA_FEATURES = "extra_features"
ATTR_FEATURES = "features"
ATTR_TURBO_MODE_SUPPORTED = "turbo_mode_supported"
ATTR_AUTO_DETECT = "auto_detect"
ATTR_SLEEP_MODE = "sleep_mode"
ATTR_VOLUME = "volume"
ATTR_USE_TIME = "use_time"
ATTR_BUTTON_PRESSED = "button_pressed"

# Air Fresh
ATTR_CO2 = "co2"

# Map attributes to properties of the state object
AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON = {
    ATTR_TEMPERATURE: "temperature",
    ATTR_HUMIDITY: "humidity",
    ATTR_AIR_QUALITY_INDEX: "aqi",
    ATTR_MODE: "mode",
    ATTR_FILTER_HOURS_USED: "filter_hours_used",
    ATTR_FILTER_LIFE: "filter_life_remaining",
    ATTR_FAVORITE_LEVEL: "favorite_level",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_LED: "led",
    ATTR_MOTOR_SPEED: "motor_speed",
    ATTR_AVERAGE_AIR_QUALITY_INDEX: "average_aqi",
    ATTR_LEARN_MODE: "learn_mode",
    ATTR_EXTRA_FEATURES: "extra_features",
    ATTR_TURBO_MODE_SUPPORTED: "turbo_mode_supported",
    ATTR_BUTTON_PRESSED: "button_pressed",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_PURIFY_VOLUME: "purify_volume",
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
    ATTR_AUTO_DETECT: "auto_detect",
    ATTR_USE_TIME: "use_time",
    ATTR_BUZZER: "buzzer",
    ATTR_LED_BRIGHTNESS: "led_brightness",
    ATTR_SLEEP_MODE: "sleep_mode",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_PURIFY_VOLUME: "purify_volume",
    ATTR_USE_TIME: "use_time",
    ATTR_FILTER_RFID_PRODUCT_ID: "filter_rfid_product_id",
    ATTR_FILTER_RFID_TAG: "filter_rfid_tag",
    ATTR_FILTER_TYPE: "filter_type",
    ATTR_ILLUMINANCE: "illuminance",
    ATTR_MOTOR2_SPEED: "motor2_speed",
    ATTR_VOLUME: "volume",
    # perhaps supported but unconfirmed
    ATTR_AUTO_DETECT: "auto_detect",
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO_V7 = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_FILTER_RFID_PRODUCT_ID: "filter_rfid_product_id",
    ATTR_FILTER_RFID_TAG: "filter_rfid_tag",
    ATTR_FILTER_TYPE: "filter_type",
    ATTR_ILLUMINANCE: "illuminance",
    ATTR_MOTOR2_SPEED: "motor2_speed",
    ATTR_VOLUME: "volume",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_2S = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_BUZZER: "buzzer",
    ATTR_FILTER_RFID_PRODUCT_ID: "filter_rfid_product_id",
    ATTR_FILTER_RFID_TAG: "filter_rfid_tag",
    ATTR_FILTER_TYPE: "filter_type",
    ATTR_ILLUMINANCE: "illuminance",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_3 = {
    ATTR_TEMPERATURE: "temperature",
    ATTR_HUMIDITY: "humidity",
    ATTR_AIR_QUALITY_INDEX: "aqi",
    ATTR_MODE: "mode",
    ATTR_FILTER_HOURS_USED: "filter_hours_used",
    ATTR_FILTER_LIFE: "filter_life_remaining",
    ATTR_FAVORITE_LEVEL: "favorite_level",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_LED: "led",
    ATTR_MOTOR_SPEED: "motor_speed",
    ATTR_AVERAGE_AIR_QUALITY_INDEX: "average_aqi",
    ATTR_PURIFY_VOLUME: "purify_volume",
    ATTR_USE_TIME: "use_time",
    ATTR_BUZZER: "buzzer",
    ATTR_LED_BRIGHTNESS: "led_brightness",
    ATTR_FILTER_RFID_PRODUCT_ID: "filter_rfid_product_id",
    ATTR_FILTER_RFID_TAG: "filter_rfid_tag",
    ATTR_FILTER_TYPE: "filter_type",
    ATTR_FAN_LEVEL: "fan_level",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_V3 = {
    # Common set isn't used here. It's a very basic version of the device.
    ATTR_AIR_QUALITY_INDEX: "aqi",
    ATTR_MODE: "mode",
    ATTR_LED: "led",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_ILLUMINANCE: "illuminance",
    ATTR_FILTER_HOURS_USED: "filter_hours_used",
    ATTR_FILTER_LIFE: "filter_life_remaining",
    ATTR_MOTOR_SPEED: "motor_speed",
    # perhaps supported but unconfirmed
    ATTR_AVERAGE_AIR_QUALITY_INDEX: "average_aqi",
    ATTR_VOLUME: "volume",
    ATTR_MOTOR2_SPEED: "motor2_speed",
    ATTR_FILTER_RFID_PRODUCT_ID: "filter_rfid_product_id",
    ATTR_FILTER_RFID_TAG: "filter_rfid_tag",
    ATTR_FILTER_TYPE: "filter_type",
    ATTR_PURIFY_VOLUME: "purify_volume",
    ATTR_LEARN_MODE: "learn_mode",
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
    ATTR_EXTRA_FEATURES: "extra_features",
    ATTR_AUTO_DETECT: "auto_detect",
    ATTR_USE_TIME: "use_time",
    ATTR_BUTTON_PRESSED: "button_pressed",
}

AVAILABLE_ATTRIBUTES_AIRFRESH = {
    ATTR_TEMPERATURE: "temperature",
    ATTR_AIR_QUALITY_INDEX: "aqi",
    ATTR_AVERAGE_AIR_QUALITY_INDEX: "average_aqi",
    ATTR_CO2: "co2",
    ATTR_HUMIDITY: "humidity",
    ATTR_MODE: "mode",
    ATTR_LED: "led",
    ATTR_LED_BRIGHTNESS: "led_brightness",
    ATTR_BUZZER: "buzzer",
    ATTR_CHILD_LOCK: "child_lock",
    ATTR_FILTER_LIFE: "filter_life_remaining",
    ATTR_FILTER_HOURS_USED: "filter_hours_used",
    ATTR_USE_TIME: "use_time",
    ATTR_MOTOR_SPEED: "motor_speed",
    ATTR_EXTRA_FEATURES: "extra_features",
}

PRESET_MODES_AIRPURIFIER = ["Auto", "Silent", "Favorite", "Idle"]
OPERATION_MODES_AIRPURIFIER_PRO = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_PRO = ["Auto", "Silent", "Favorite"]
OPERATION_MODES_AIRPURIFIER_PRO_V7 = OPERATION_MODES_AIRPURIFIER_PRO
PRESET_MODES_AIRPURIFIER_PRO_V7 = PRESET_MODES_AIRPURIFIER_PRO
OPERATION_MODES_AIRPURIFIER_2S = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_2S = ["Auto", "Silent", "Favorite"]
OPERATION_MODES_AIRPURIFIER_3 = ["Auto", "Silent", "Favorite", "Fan"]
PRESET_MODES_AIRPURIFIER_3 = ["Auto", "Silent", "Favorite", "Fan"]
OPERATION_MODES_AIRPURIFIER_V3 = [
    "Auto",
    "Silent",
    "Favorite",
    "Idle",
    "Medium",
    "High",
    "Strong",
]
PRESET_MODES_AIRPURIFIER_V3 = [
    "Auto",
    "Silent",
    "Favorite",
    "Idle",
    "Medium",
    "High",
    "Strong",
]
OPERATION_MODES_AIRFRESH = ["Auto", "Silent", "Interval", "Low", "Middle", "Strong"]
PRESET_MODES_AIRFRESH = ["Auto", "Interval"]

FEATURE_FLAGS_AIRPURIFIER = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_LEARN_MODE
    | FEATURE_RESET_FILTER
    | FEATURE_SET_EXTRA_FEATURES
)

FEATURE_FLAGS_AIRPURIFIER_PRO = (
    FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_AUTO_DETECT
    | FEATURE_SET_VOLUME
)

FEATURE_FLAGS_AIRPURIFIER_PRO_V7 = (
    FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_VOLUME
)

FEATURE_FLAGS_AIRPURIFIER_2S = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
)

FEATURE_FLAGS_AIRPURIFIER_3 = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_FAVORITE_LEVEL
    | FEATURE_SET_FAN_LEVEL
    | FEATURE_SET_LED_BRIGHTNESS
)

FEATURE_FLAGS_AIRPURIFIER_V3 = (
    FEATURE_SET_BUZZER | FEATURE_SET_CHILD_LOCK | FEATURE_SET_LED
)

FEATURE_FLAGS_AIRFRESH = (
    FEATURE_SET_BUZZER
    | FEATURE_SET_CHILD_LOCK
    | FEATURE_SET_LED
    | FEATURE_SET_LED_BRIGHTNESS
    | FEATURE_RESET_FILTER
    | FEATURE_SET_EXTRA_FEATURES
)

AIRPURIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_LED_BRIGHTNESS = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_BRIGHTNESS): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=2))}
)

SERVICE_SCHEMA_FAVORITE_LEVEL = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=17))}
)

SERVICE_SCHEMA_FAN_LEVEL = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_LEVEL): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3))}
)

SERVICE_SCHEMA_VOLUME = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_VOLUME): vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100))}
)

SERVICE_SCHEMA_EXTRA_FEATURES = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_FEATURES): cv.positive_int}
)

SERVICE_TO_METHOD = {
    SERVICE_SET_BUZZER_ON: {"method": "async_set_buzzer_on"},
    SERVICE_SET_BUZZER_OFF: {"method": "async_set_buzzer_off"},
    SERVICE_SET_FAN_LED_ON: {"method": "async_set_led_on"},
    SERVICE_SET_FAN_LED_OFF: {"method": "async_set_led_off"},
    SERVICE_SET_CHILD_LOCK_ON: {"method": "async_set_child_lock_on"},
    SERVICE_SET_CHILD_LOCK_OFF: {"method": "async_set_child_lock_off"},
    SERVICE_SET_AUTO_DETECT_ON: {"method": "async_set_auto_detect_on"},
    SERVICE_SET_AUTO_DETECT_OFF: {"method": "async_set_auto_detect_off"},
    SERVICE_SET_LEARN_MODE_ON: {"method": "async_set_learn_mode_on"},
    SERVICE_SET_LEARN_MODE_OFF: {"method": "async_set_learn_mode_off"},
    SERVICE_RESET_FILTER: {"method": "async_reset_filter"},
    SERVICE_SET_LED_BRIGHTNESS: {
        "method": "async_set_led_brightness",
        "schema": SERVICE_SCHEMA_LED_BRIGHTNESS,
    },
    SERVICE_SET_FAVORITE_LEVEL: {
        "method": "async_set_favorite_level",
        "schema": SERVICE_SCHEMA_FAVORITE_LEVEL,
    },
    SERVICE_SET_FAN_LEVEL: {
        "method": "async_set_fan_level",
        "schema": SERVICE_SCHEMA_FAN_LEVEL,
    },
    SERVICE_SET_VOLUME: {"method": "async_set_volume", "schema": SERVICE_SCHEMA_VOLUME},
    SERVICE_SET_EXTRA_FEATURES: {
        "method": "async_set_extra_features",
        "schema": SERVICE_SCHEMA_EXTRA_FEATURES,
    },
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Import Miio configuration from YAML."""
    _LOGGER.warning(
        "Loading Xiaomi Miio Fan via platform setup is deprecated. "
        "Please remove it from your configuration"
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


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

        if model in MODELS_PURIFIER_MIOT:
            air_purifier = AirPurifierMiot(host, token)
            entity = XiaomiAirPurifierMiot(
                name, air_purifier, config_entry, unique_id, allowed_failures=2
            )
        elif model.startswith("zhimi.airpurifier."):
            air_purifier = AirPurifier(host, token)
            entity = XiaomiAirPurifier(name, air_purifier, config_entry, unique_id)
        elif model.startswith("zhimi.airfresh."):
            air_fresh = AirFresh(host, token)
            entity = XiaomiAirFresh(name, air_fresh, config_entry, unique_id)
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

        for air_purifier_service, method in SERVICE_TO_METHOD.items():
            schema = method.get("schema", AIRPURIFIER_SERVICE_SCHEMA)
            hass.services.async_register(
                DOMAIN, air_purifier_service, async_service_handler, schema=schema
            )

    async_add_entities(entities, update_before_add=True)


class XiaomiGenericDevice(XiaomiMiioEntity, FanEntity):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, entry, unique_id):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id)

        self._available = False
        self._state = None
        self._state_attrs = {ATTR_MODEL: self._model}
        self._device_features = FEATURE_SET_CHILD_LOCK
        self._skip_update = False
        self._supported_features = 0
        self._speed_count = 100
        self._preset_modes = []
        # the speed_list attribute is deprecated, support will end with release 2021.7
        self._speed_list = []

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    # the speed_list attribute is deprecated, support will end with release 2021.7
    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return self._speed_list

    @property
    def speed_count(self):
        """Return the number of speeds of the fan supported."""
        return self._speed_count

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def percentage(self):
        """Return the percentage based speed of the fan."""
        return None

    @property
    def preset_mode(self):
        """Return the percentage based speed of the fan."""
        return None

    @property
    def should_poll(self):
        """Poll the device."""
        return True

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def extra_state_attributes(self):
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

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        # Remove the async_set_speed call is async_set_percentage and async_set_preset_modes have been implemented
        if speed:
            await self.async_set_speed(speed)
        # If operation mode was set the device must not be turned on.
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)
        else:
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


class XiaomiAirPurifier(XiaomiGenericDevice):
    """Representation of a Xiaomi Air Purifier."""

    PRESET_MODE_MAPPING = {
        "Auto": AirpurifierOperationMode.Auto,
        "Silent": AirpurifierOperationMode.Silent,
        "Favorite": AirpurifierOperationMode.Favorite,
        "Idle": AirpurifierOperationMode.Favorite,
    }

    SPEED_MODE_MAPPING = {
        1: AirpurifierOperationMode.Silent,
        2: AirpurifierOperationMode.Medium,
        3: AirpurifierOperationMode.High,
        4: AirpurifierOperationMode.Strong,
    }

    REVERSE_SPEED_MODE_MAPPING = {v: k for k, v in SPEED_MODE_MAPPING.items()}

    def __init__(self, name, device, entry, unique_id, allowed_failures=0):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id)
        self._allowed_failures = allowed_failures
        self._failure = 0

        if self._model == MODEL_AIRPURIFIER_PRO:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO
            # SUPPORT_SET_SPEED was disabled
            # the device supports preset_modes only
            self._preset_modes = PRESET_MODES_AIRPURIFIER_PRO
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = OPERATION_MODES_AIRPURIFIER_PRO
        elif self._model == MODEL_AIRPURIFIER_PRO_V7:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO_V7
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO_V7
            # SUPPORT_SET_SPEED was disabled
            # the device supports preset_modes only
            self._preset_modes = PRESET_MODES_AIRPURIFIER_PRO_V7
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = OPERATION_MODES_AIRPURIFIER_PRO_V7
        elif self._model in [MODEL_AIRPURIFIER_2S, MODEL_AIRPURIFIER_2H]:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_2S
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_2S
            # SUPPORT_SET_SPEED was disabled
            # the device supports preset_modes only
            self._preset_modes = PRESET_MODES_AIRPURIFIER_2S
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = OPERATION_MODES_AIRPURIFIER_2S
        elif self._model in MODELS_PURIFIER_MIOT:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_3
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_3
            # SUPPORT_SET_SPEED was disabled
            # the device supports preset_modes only
            self._preset_modes = PRESET_MODES_AIRPURIFIER_3
            self._supported_features = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE
            self._speed_count = 3
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = OPERATION_MODES_AIRPURIFIER_3
        elif self._model == MODEL_AIRPURIFIER_V3:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_V3
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_V3
            # SUPPORT_SET_SPEED was disabled
            # the device supports preset_modes only
            self._preset_modes = PRESET_MODES_AIRPURIFIER_V3
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = OPERATION_MODES_AIRPURIFIER_V3
        else:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER
            self._preset_modes = PRESET_MODES_AIRPURIFIER
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
            # the speed_list attribute is deprecated, support will end with release 2021.7
            self._speed_list = []

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
            self._state_attrs.update(
                {
                    key: self._extract_value_from_attribute(state, value)
                    for key, value in self._available_attributes.items()
                }
            )

            self._failure = 0

        except DeviceException as ex:
            self._failure += 1
            if self._failure < self._allowed_failures:
                _LOGGER.info(
                    "Got exception while fetching the state: %s, failure: %d",
                    ex,
                    self._failure,
                )
            else:
                if self._available:
                    self._available = False
                    _LOGGER.error(
                        "Got exception while fetching the state: %s, failure: %d",
                        ex,
                        self._failure,
                    )

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        if self._state:
            preset_mode = AirpurifierOperationMode(self._state_attrs[ATTR_MODE]).name
            return preset_mode if preset_mode in self._preset_modes else None

        return None

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._state:
            mode = AirpurifierOperationMode(self._state_attrs[ATTR_MODE])
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self._speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
                )

        return None

    # the speed attribute is deprecated, support will end with release 2021.7
    @property
    def speed(self):
        """Return the current speed."""
        if self._state:
            return AirpurifierOperationMode(self._state_attrs[ATTR_MODE]).name

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        speed_mode = math.ceil(
            percentage_to_ranged_value((1, self._speed_count), percentage)
        )
        if speed_mode:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                AirpurifierOperationMode(self.SPEED_MODE_MAPPING[speed_mode]),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.PRESET_MODE_MAPPING[preset_mode],
        )

    # the async_set_speed function is deprecated, support will end with release 2021.7
    # it is added here only for compatibility with legacy speeds
    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self.supported_features & SUPPORT_SET_SPEED == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", speed)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirpurifierOperationMode[speed.title()],
        )

    async def async_set_led_on(self):
        """Turn the led on."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.", self._device.set_led, True
        )

    async def async_set_led_off(self):
        """Turn the led off."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.",
            self._device.set_led,
            False,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirpurifierLedBrightness(brightness),
        )

    async def async_set_favorite_level(self, level: int = 1):
        """Set the favorite level."""
        if self._device_features & FEATURE_SET_FAVORITE_LEVEL == 0:
            return

        await self._try_command(
            "Setting the favorite level of the miio device failed.",
            self._device.set_favorite_level,
            level,
        )

    async def async_set_fan_level(self, level: int = 1):
        """Set the favorite level."""
        if self._device_features & FEATURE_SET_FAN_LEVEL == 0:
            return

        await self._try_command(
            "Setting the fan level of the miio device failed.",
            self._device.set_fan_level,
            level,
        )

    async def async_set_auto_detect_on(self):
        """Turn the auto detect on."""
        if self._device_features & FEATURE_SET_AUTO_DETECT == 0:
            return

        await self._try_command(
            "Turning the auto detect of the miio device on failed.",
            self._device.set_auto_detect,
            True,
        )

    async def async_set_auto_detect_off(self):
        """Turn the auto detect off."""
        if self._device_features & FEATURE_SET_AUTO_DETECT == 0:
            return

        await self._try_command(
            "Turning the auto detect of the miio device off failed.",
            self._device.set_auto_detect,
            False,
        )

    async def async_set_learn_mode_on(self):
        """Turn the learn mode on."""
        if self._device_features & FEATURE_SET_LEARN_MODE == 0:
            return

        await self._try_command(
            "Turning the learn mode of the miio device on failed.",
            self._device.set_learn_mode,
            True,
        )

    async def async_set_learn_mode_off(self):
        """Turn the learn mode off."""
        if self._device_features & FEATURE_SET_LEARN_MODE == 0:
            return

        await self._try_command(
            "Turning the learn mode of the miio device off failed.",
            self._device.set_learn_mode,
            False,
        )

    async def async_set_volume(self, volume: int = 50):
        """Set the sound volume."""
        if self._device_features & FEATURE_SET_VOLUME == 0:
            return

        await self._try_command(
            "Setting the sound volume of the miio device failed.",
            self._device.set_volume,
            volume,
        )

    async def async_set_extra_features(self, features: int = 1):
        """Set the extra features."""
        if self._device_features & FEATURE_SET_EXTRA_FEATURES == 0:
            return

        await self._try_command(
            "Setting the extra features of the miio device failed.",
            self._device.set_extra_features,
            features,
        )

    async def async_reset_filter(self):
        """Reset the filter lifetime and usage."""
        if self._device_features & FEATURE_RESET_FILTER == 0:
            return

        await self._try_command(
            "Resetting the filter lifetime of the miio device failed.",
            self._device.reset_filter,
        )


class XiaomiAirPurifierMiot(XiaomiAirPurifier):
    """Representation of a Xiaomi Air Purifier (MiOT protocol)."""

    PRESET_MODE_MAPPING = {
        "Auto": AirpurifierMiotOperationMode.Auto,
        "Silent": AirpurifierMiotOperationMode.Silent,
        "Favorite": AirpurifierMiotOperationMode.Favorite,
        "Fan": AirpurifierMiotOperationMode.Fan,
    }

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._state:
            fan_level = self._state_attrs[ATTR_FAN_LEVEL]
            return ranged_value_to_percentage((1, 3), fan_level)

        return None

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        if self._state:
            preset_mode = AirpurifierMiotOperationMode(
                self._state_attrs[ATTR_MODE]
            ).name
            return preset_mode if preset_mode in self._preset_modes else None

        return None

    # the speed attribute is deprecated, support will end with release 2021.7
    @property
    def speed(self):
        """Return the current speed."""
        if self._state:
            return AirpurifierMiotOperationMode(self._state_attrs[ATTR_MODE]).name

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        fan_level = math.ceil(percentage_to_ranged_value((1, 3), percentage))
        if fan_level:
            await self._try_command(
                "Setting fan level of the miio device failed.",
                self._device.set_fan_level,
                fan_level,
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.PRESET_MODE_MAPPING[preset_mode],
        )

    # the async_set_speed function is deprecated, support will end with release 2021.7
    # it is added here only for compatibility with legacy speeds
    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self.supported_features & SUPPORT_SET_SPEED == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", speed)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirpurifierMiotOperationMode[speed.title()],
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirpurifierMiotLedBrightness(brightness),
        )


class XiaomiAirFresh(XiaomiGenericDevice):
    """Representation of a Xiaomi Air Fresh."""

    SPEED_MODE_MAPPING = {
        1: AirfreshOperationMode.Silent,
        2: AirfreshOperationMode.Low,
        3: AirfreshOperationMode.Middle,
        4: AirfreshOperationMode.Strong,
    }

    REVERSE_SPEED_MODE_MAPPING = {v: k for k, v in SPEED_MODE_MAPPING.items()}

    PRESET_MODE_MAPPING = {
        "Auto": AirfreshOperationMode.Auto,
        "Interval": AirfreshOperationMode.Interval,
    }

    def __init__(self, name, device, entry, unique_id):
        """Initialize the miio device."""
        super().__init__(name, device, entry, unique_id)

        self._device_features = FEATURE_FLAGS_AIRFRESH
        self._available_attributes = AVAILABLE_ATTRIBUTES_AIRFRESH
        # the speed_list attribute is deprecated, support will end with release 2021.7
        self._speed_list = OPERATION_MODES_AIRFRESH
        self._speed_count = 4
        self._preset_modes = PRESET_MODES_AIRFRESH
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
    def preset_mode(self):
        """Get the active preset mode."""
        if self._state:
            preset_mode = AirfreshOperationMode(self._state_attrs[ATTR_MODE]).name
            return preset_mode if preset_mode in self._preset_modes else None

        return None

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._state:
            mode = AirfreshOperationMode(self._state_attrs[ATTR_MODE])
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self._speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
                )

        return None

    # the speed attribute is deprecated, support will end with release 2021.7
    @property
    def speed(self):
        """Return the current speed."""
        if self._state:
            return AirfreshOperationMode(self._state_attrs[ATTR_MODE]).name

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        speed_mode = math.ceil(
            percentage_to_ranged_value((1, self._speed_count), percentage)
        )
        if speed_mode:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                AirfreshOperationMode(self.SPEED_MODE_MAPPING[speed_mode]),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.PRESET_MODE_MAPPING[preset_mode],
        )

    # the async_set_speed function is deprecated, support will end with release 2021.7
    # it is added here only for compatibility with legacy speeds
    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if self.supported_features & SUPPORT_SET_SPEED == 0:
            return

        _LOGGER.debug("Setting the operation mode to: %s", speed)

        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            AirfreshOperationMode[speed.title()],
        )

    async def async_set_led_on(self):
        """Turn the led on."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.", self._device.set_led, True
        )

    async def async_set_led_off(self):
        """Turn the led off."""
        if self._device_features & FEATURE_SET_LED == 0:
            return

        await self._try_command(
            "Turning the led of the miio device off failed.",
            self._device.set_led,
            False,
        )

    async def async_set_led_brightness(self, brightness: int = 2):
        """Set the led brightness."""
        if self._device_features & FEATURE_SET_LED_BRIGHTNESS == 0:
            return

        await self._try_command(
            "Setting the led brightness of the miio device failed.",
            self._device.set_led_brightness,
            AirfreshLedBrightness(brightness),
        )

    async def async_set_extra_features(self, features: int = 1):
        """Set the extra features."""
        if self._device_features & FEATURE_SET_EXTRA_FEATURES == 0:
            return

        await self._try_command(
            "Setting the extra features of the miio device failed.",
            self._device.set_extra_features,
            features,
        )

    async def async_reset_filter(self):
        """Reset the filter lifetime and usage."""
        if self._device_features & FEATURE_RESET_FILTER == 0:
            return

        await self._try_command(
            "Resetting the filter lifetime of the miio device failed.",
            self._device.reset_filter,
        )
