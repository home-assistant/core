"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier."""
from abc import abstractmethod
import asyncio
from enum import Enum
import logging
import math

from miio.airfresh import OperationMode as AirfreshOperationMode
from miio.airpurifier import OperationMode as AirpurifierOperationMode
from miio.airpurifier_miot import OperationMode as AirpurifierMiotOperationMode
from miio.fan import (
    MoveDirection as FanMoveDirection,
    OperationMode as FanOperationMode,
)
from miio.fan_miot import (
    OperationMode as FanMiotOperationMode,
    OperationModeFanZA5 as FanZA5OperationMode,
)
import voluptuous as vol

from homeassistant.components.fan import (
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_PRESET_MODE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    DOMAIN,
    FEATURE_FLAGS_AIRFRESH,
    FEATURE_FLAGS_AIRPURIFIER_2S,
    FEATURE_FLAGS_AIRPURIFIER_3C,
    FEATURE_FLAGS_AIRPURIFIER_MIIO,
    FEATURE_FLAGS_AIRPURIFIER_MIOT,
    FEATURE_FLAGS_AIRPURIFIER_PRO,
    FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    FEATURE_FLAGS_AIRPURIFIER_V3,
    FEATURE_FLAGS_FAN,
    FEATURE_FLAGS_FAN_1C,
    FEATURE_FLAGS_FAN_P5,
    FEATURE_FLAGS_FAN_P9,
    FEATURE_FLAGS_FAN_P10_P11,
    FEATURE_FLAGS_FAN_ZA5,
    FEATURE_RESET_FILTER,
    FEATURE_SET_EXTRA_FEATURES,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODEL_AIRPURIFIER_2H,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V3,
    MODEL_FAN_1C,
    MODEL_FAN_P5,
    MODEL_FAN_P9,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_ZA5,
    MODELS_FAN_MIIO,
    MODELS_FAN_MIOT,
    MODELS_PURIFIER_MIOT,
    SERVICE_RESET_FILTER,
    SERVICE_SET_EXTRA_FEATURES,
)
from .device import XiaomiCoordinatedMiioEntity

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "fan.xiaomi_miio"

CONF_MODEL = "model"

ATTR_MODE_NATURE = "Nature"
ATTR_MODE_NORMAL = "Normal"

# Air Purifier
ATTR_BRIGHTNESS = "brightness"
ATTR_FAN_LEVEL = "fan_level"
ATTR_SLEEP_TIME = "sleep_time"
ATTR_SLEEP_LEARN_COUNT = "sleep_mode_learn_count"
ATTR_EXTRA_FEATURES = "extra_features"
ATTR_FEATURES = "features"
ATTR_TURBO_MODE_SUPPORTED = "turbo_mode_supported"
ATTR_SLEEP_MODE = "sleep_mode"
ATTR_USE_TIME = "use_time"
ATTR_BUTTON_PRESSED = "button_pressed"

# Map attributes to properties of the state object
AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON = {
    ATTR_EXTRA_FEATURES: "extra_features",
    ATTR_TURBO_MODE_SUPPORTED: "turbo_mode_supported",
    ATTR_BUTTON_PRESSED: "button_pressed",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
    ATTR_USE_TIME: "use_time",
    ATTR_SLEEP_MODE: "sleep_mode",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO = {
    **AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON,
    ATTR_USE_TIME: "use_time",
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT = {ATTR_USE_TIME: "use_time"}

AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO_V7 = AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON

AVAILABLE_ATTRIBUTES_AIRPURIFIER_V3 = {
    # Common set isn't used here. It's a very basic version of the device.
    ATTR_SLEEP_TIME: "sleep_time",
    ATTR_SLEEP_LEARN_COUNT: "sleep_mode_learn_count",
    ATTR_EXTRA_FEATURES: "extra_features",
    ATTR_USE_TIME: "use_time",
    ATTR_BUTTON_PRESSED: "button_pressed",
}

AVAILABLE_ATTRIBUTES_AIRFRESH = {
    ATTR_USE_TIME: "use_time",
    ATTR_EXTRA_FEATURES: "extra_features",
}

PRESET_MODES_AIRPURIFIER = ["Auto", "Silent", "Favorite", "Idle"]
PRESET_MODES_AIRPURIFIER_MIOT = ["Auto", "Silent", "Favorite", "Fan"]
PRESET_MODES_AIRPURIFIER_PRO = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_PRO_V7 = PRESET_MODES_AIRPURIFIER_PRO
PRESET_MODES_AIRPURIFIER_2S = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_3C = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_V3 = [
    "Auto",
    "Silent",
    "Favorite",
    "Idle",
    "Medium",
    "High",
    "Strong",
]
PRESET_MODES_AIRFRESH = ["Auto", "Interval"]

AIRPURIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_EXTRA_FEATURES = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_FEATURES): cv.positive_int}
)

SERVICE_TO_METHOD = {
    SERVICE_RESET_FILTER: {"method": "async_reset_filter"},
    SERVICE_SET_EXTRA_FEATURES: {
        "method": "async_set_extra_features",
        "schema": SERVICE_SCHEMA_EXTRA_FEATURES,
    },
}

FAN_DIRECTIONS_MAP = {
    "forward": "right",
    "reverse": "left",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Fan from a config entry."""
    entities = []

    if not config_entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        return

    hass.data.setdefault(DATA_KEY, {})

    name = config_entry.title
    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    coordinator = hass.data[DOMAIN][config_entry.entry_id][KEY_COORDINATOR]
    device = hass.data[DOMAIN][config_entry.entry_id][KEY_DEVICE]

    if model == MODEL_AIRPURIFIER_3C:
        entity = XiaomiAirPurifierMB4(
            name,
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    elif model in MODELS_PURIFIER_MIOT:
        entity = XiaomiAirPurifierMiot(
            name,
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    elif model.startswith("zhimi.airpurifier."):
        entity = XiaomiAirPurifier(name, device, config_entry, unique_id, coordinator)
    elif model.startswith("zhimi.airfresh."):
        entity = XiaomiAirFresh(name, device, config_entry, unique_id, coordinator)
    elif model == MODEL_FAN_P5:
        entity = XiaomiFanP5(name, device, config_entry, unique_id, coordinator)
    elif model in MODELS_FAN_MIIO:
        entity = XiaomiFan(name, device, config_entry, unique_id, coordinator)
    elif model == MODEL_FAN_ZA5:
        entity = XiaomiFanZA5(name, device, config_entry, unique_id, coordinator)
    elif model in MODELS_FAN_MIOT:
        entity = XiaomiFanMiot(name, device, config_entry, unique_id, coordinator)
    else:
        return

    hass.data[DATA_KEY][unique_id] = entity

    entities.append(entity)

    async def async_service_handler(service):
        """Map services to methods on XiaomiAirPurifier."""
        method = SERVICE_TO_METHOD[service.service]
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            filtered_entities = [
                entity
                for entity in hass.data[DATA_KEY].values()
                if entity.entity_id in entity_ids
            ]
        else:
            filtered_entities = hass.data[DATA_KEY].values()

        update_tasks = []

        for entity in filtered_entities:
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

    async_add_entities(entities)


class XiaomiGenericDevice(XiaomiCoordinatedMiioEntity, FanEntity):
    """Representation of a generic Xiaomi device."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the generic Xiaomi device."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._available_attributes = {}
        self._state = None
        self._mode = None
        self._fan_level = None
        self._state_attrs = {}
        self._device_features = 0
        self._supported_features = 0
        self._preset_modes = []

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    @abstractmethod
    def operation_mode_class(self):
        """Hold operation mode class."""

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        return self._preset_modes

    @property
    def percentage(self):
        """Return the percentage based speed of the fan."""
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.", self._device.on
        )

        # If operation mode was set the device must not be turned on.
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)

        if result:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.", self._device.off
        )

        if result:
            self._state = False
            self.async_write_ha_state()


class XiaomiGenericAirPurifier(XiaomiGenericDevice):
    """Representation of a generic AirPurifier device."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the generic AirPurifier device."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._speed_count = 100

    @property
    def speed_count(self):
        """Return the number of speeds of the fan supported."""
        return self._speed_count

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        if self._state:
            preset_mode = self.operation_mode_class(self._mode).name
            return preset_mode if preset_mode in self._preset_modes else None

        return None

    @staticmethod
    def _extract_value_from_attribute(state, attribute):
        value = getattr(state, attribute)
        if isinstance(value, Enum):
            return value.value

        return value

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._state_attrs.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in self._available_attributes.items()
            }
        )
        self._mode = self.coordinator.data.mode.value
        self._fan_level = getattr(self.coordinator.data, ATTR_FAN_LEVEL, None)
        self.async_write_ha_state()


class XiaomiAirPurifier(XiaomiGenericAirPurifier):
    """Representation of a Xiaomi Air Purifier."""

    SPEED_MODE_MAPPING = {
        1: AirpurifierOperationMode.Silent,
        2: AirpurifierOperationMode.Medium,
        3: AirpurifierOperationMode.High,
        4: AirpurifierOperationMode.Strong,
    }

    REVERSE_SPEED_MODE_MAPPING = {v: k for k, v in SPEED_MODE_MAPPING.items()}

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the plug switch."""
        super().__init__(name, device, entry, unique_id, coordinator)

        if self._model == MODEL_AIRPURIFIER_PRO:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO
            self._preset_modes = PRESET_MODES_AIRPURIFIER_PRO
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
        elif self._model == MODEL_AIRPURIFIER_PRO_V7:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO_V7
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO_V7
            self._preset_modes = PRESET_MODES_AIRPURIFIER_PRO_V7
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
        elif self._model in [MODEL_AIRPURIFIER_2S, MODEL_AIRPURIFIER_2H]:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_2S
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON
            self._preset_modes = PRESET_MODES_AIRPURIFIER_2S
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
        elif self._model in MODELS_PURIFIER_MIOT:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_MIOT
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT
            self._preset_modes = PRESET_MODES_AIRPURIFIER_MIOT
            self._supported_features = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE
            self._speed_count = 3
        elif self._model == MODEL_AIRPURIFIER_V3:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_V3
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_V3
            self._preset_modes = PRESET_MODES_AIRPURIFIER_V3
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1
        else:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_MIIO
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER
            self._preset_modes = PRESET_MODES_AIRPURIFIER
            self._supported_features = SUPPORT_PRESET_MODE
            self._speed_count = 1

        self._state = self.coordinator.data.is_on
        self._state_attrs.update(
            {
                key: self._extract_value_from_attribute(self.coordinator.data, value)
                for key, value in self._available_attributes.items()
            }
        )
        self._mode = self.coordinator.data.mode.value
        self._fan_level = getattr(self.coordinator.data, ATTR_FAN_LEVEL, None)

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirpurifierOperationMode

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._state:
            mode = self.operation_mode_class(self._mode)
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self._speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
                )

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        if percentage == 0:
            await self.async_turn_off()
            return

        speed_mode = math.ceil(
            percentage_to_ranged_value((1, self._speed_count), percentage)
        )
        if speed_mode:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                self.operation_mode_class(self.SPEED_MODE_MAPPING[speed_mode]),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.operation_mode_class[preset_mode],
        ):
            self._mode = self.operation_mode_class[preset_mode].value
            self.async_write_ha_state()

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

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirpurifierMiotOperationMode

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._fan_level is None:
            return None
        if self._state:
            return ranged_value_to_percentage((1, 3), self._fan_level)

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        if percentage == 0:
            await self.async_turn_off()
            return

        fan_level = math.ceil(percentage_to_ranged_value((1, 3), percentage))
        if not fan_level:
            return
        if await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_fan_level,
            fan_level,
        ):
            self._fan_level = fan_level
            self.async_write_ha_state()


class XiaomiAirPurifierMB4(XiaomiGenericAirPurifier):
    """Representation of a Xiaomi Air Purifier MB4."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize Air Purifier MB4."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._device_features = FEATURE_FLAGS_AIRPURIFIER_3C
        self._preset_modes = PRESET_MODES_AIRPURIFIER_3C
        self._supported_features = SUPPORT_PRESET_MODE

        self._state = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirpurifierMiotOperationMode

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.operation_mode_class[preset_mode],
        ):
            self._mode = self.operation_mode_class[preset_mode].value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value
        self.async_write_ha_state()


class XiaomiAirFresh(XiaomiGenericAirPurifier):
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

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the miio device."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._device_features = FEATURE_FLAGS_AIRFRESH
        self._available_attributes = AVAILABLE_ATTRIBUTES_AIRFRESH
        self._speed_count = 4
        self._preset_modes = PRESET_MODES_AIRFRESH
        self._supported_features = SUPPORT_SET_SPEED | SUPPORT_PRESET_MODE

        self._state = self.coordinator.data.is_on
        self._state_attrs.update(
            {
                key: getattr(self.coordinator.data, value)
                for key, value in self._available_attributes.items()
            }
        )
        self._mode = self.coordinator.data.mode.value

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirfreshOperationMode

    @property
    def percentage(self):
        """Return the current percentage based speed."""
        if self._state:
            mode = AirfreshOperationMode(self._mode)
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self._speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
                )

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        speed_mode = math.ceil(
            percentage_to_ranged_value((1, self._speed_count), percentage)
        )
        if speed_mode:
            if await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,
                AirfreshOperationMode(self.SPEED_MODE_MAPPING[speed_mode]),
            ):
                self._mode = AirfreshOperationMode(
                    self.SPEED_MODE_MAPPING[speed_mode]
                ).value
                self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.operation_mode_class[preset_mode],
        ):
            self._mode = self.operation_mode_class[preset_mode].value
            self.async_write_ha_state()

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


class XiaomiGenericFan(XiaomiGenericDevice):
    """Representation of a generic Xiaomi Fan."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the fan."""
        super().__init__(name, device, entry, unique_id, coordinator)

        if self._model == MODEL_FAN_P5:
            self._device_features = FEATURE_FLAGS_FAN_P5
        elif self._model == MODEL_FAN_ZA5:
            self._device_features = FEATURE_FLAGS_FAN_ZA5
        elif self._model == MODEL_FAN_1C:
            self._device_features = FEATURE_FLAGS_FAN_1C
        elif self._model == MODEL_FAN_P9:
            self._device_features = FEATURE_FLAGS_FAN_P9
        elif self._model in (MODEL_FAN_P10, MODEL_FAN_P11):
            self._device_features = FEATURE_FLAGS_FAN_P10_P11
        else:
            self._device_features = FEATURE_FLAGS_FAN
        self._supported_features = (
            SUPPORT_SET_SPEED | SUPPORT_OSCILLATE | SUPPORT_PRESET_MODE
        )
        if self._model != MODEL_FAN_1C:
            self._supported_features |= SUPPORT_DIRECTION
        self._preset_mode = None
        self._oscillating = None
        self._percentage = None

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        return self._preset_mode

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        return [mode.name for mode in self.operation_mode_class]

    @property
    def percentage(self):
        """Return the current speed as a percentage."""
        if self._state:
            return self._percentage

        return None

    @property
    def oscillating(self):
        """Return whether or not the fan is currently oscillating."""
        return self._oscillating

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        await self._try_command(
            "Setting oscillate on/off of the miio device failed.",
            self._device.set_oscillate,
            oscillating,
        )
        self._oscillating = oscillating
        self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if self._oscillating:
            await self.async_oscillate(oscillating=False)

        await self._try_command(
            "Setting move direction of the miio device failed.",
            self._device.set_rotate,
            FanMoveDirection(FAN_DIRECTIONS_MAP[direction]),
        )


class XiaomiFan(XiaomiGenericFan):
    """Representation of a Xiaomi Fan."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the fan."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._state = self.coordinator.data.is_on
        self._oscillating = self.coordinator.data.oscillate
        self._nature_mode = self.coordinator.data.natural_speed != 0
        if self._nature_mode:
            self._percentage = self.coordinator.data.natural_speed
        else:
            self._percentage = self.coordinator.data.direct_speed

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        return ATTR_MODE_NATURE if self._nature_mode else ATTR_MODE_NORMAL

    @property
    def preset_modes(self) -> list:
        """Get the list of available preset modes."""
        return [ATTR_MODE_NATURE, ATTR_MODE_NORMAL]

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._oscillating = self.coordinator.data.oscillate
        self._nature_mode = self.coordinator.data.natural_speed != 0
        if self._nature_mode:
            self._percentage = self.coordinator.data.natural_speed
        else:
            self._percentage = self.coordinator.data.direct_speed

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return

        if preset_mode == ATTR_MODE_NATURE:
            await self._try_command(
                "Setting natural fan speed percentage of the miio device failed.",
                self._device.set_natural_speed,
                self._percentage,
            )
        else:
            await self._try_command(
                "Setting direct fan speed percentage of the miio device failed.",
                self._device.set_direct_speed,
                self._percentage,
            )

        self._preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        if self._nature_mode:
            await self._try_command(
                "Setting fan speed percentage of the miio device failed.",
                self._device.set_natural_speed,
                percentage,
            )
        else:
            await self._try_command(
                "Setting fan speed percentage of the miio device failed.",
                self._device.set_direct_speed,
                percentage,
            )
        self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        else:
            self.async_write_ha_state()


class XiaomiFanP5(XiaomiGenericFan):
    """Representation of a Xiaomi Fan P5."""

    def __init__(self, name, device, entry, unique_id, coordinator):
        """Initialize the fan."""
        super().__init__(name, device, entry, unique_id, coordinator)

        self._state = self.coordinator.data.is_on
        self._preset_mode = self.coordinator.data.mode.name
        self._oscillating = self.coordinator.data.oscillate
        self._percentage = self.coordinator.data.speed

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return FanOperationMode

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._preset_mode = self.coordinator.data.mode.name
        self._oscillating = self.coordinator.data.oscillate
        self._percentage = self.coordinator.data.speed

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.operation_mode_class[preset_mode],
        )
        self._preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )
        self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        else:
            self.async_write_ha_state()


class XiaomiFanMiot(XiaomiGenericFan):
    """Representation of a Xiaomi Fan Miot."""

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return FanMiotOperationMode

    @property
    def preset_mode(self):
        """Get the active preset mode."""
        return self._preset_mode

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._state = self.coordinator.data.is_on
        self._preset_mode = self.coordinator.data.mode.name
        self._oscillating = self.coordinator.data.oscillate
        if self.coordinator.data.is_on:
            self._percentage = self.coordinator.data.fan_speed
        else:
            self._percentage = 0

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode not in self.preset_modes:
            _LOGGER.warning("'%s'is not a valid preset mode", preset_mode)
            return
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,
            self.operation_mode_class[preset_mode],
        )
        self._preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,
            percentage,
        )
        self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        else:
            self.async_write_ha_state()


class XiaomiFanZA5(XiaomiFanMiot):
    """Representation of a Xiaomi Fan ZA5."""

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return FanZA5OperationMode
