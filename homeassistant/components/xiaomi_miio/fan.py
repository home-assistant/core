"""Support for Xiaomi Mi Air Purifier and Xiaomi Mi Air Humidifier."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
import logging
import math
from typing import Any

from miio import Device as MiioDevice
from miio.fan_common import (
    MoveDirection as FanMoveDirection,
    OperationMode as FanOperationMode,
)
from miio.integrations.airpurifier.dmaker.airfresh_t2017 import (
    OperationMode as AirfreshOperationModeT2017,
)
from miio.integrations.airpurifier.zhimi.airfresh import (
    OperationMode as AirfreshOperationMode,
)
from miio.integrations.airpurifier.zhimi.airpurifier import (
    OperationMode as AirpurifierOperationMode,
)
from miio.integrations.airpurifier.zhimi.airpurifier_miot import (
    OperationMode as AirpurifierMiotOperationMode,
)
from miio.integrations.fan.dmaker.fan import FanStatusP5
from miio.integrations.fan.dmaker.fan_miot import FanStatusMiot
from miio.integrations.fan.zhimi.zhimi_miot import (
    OperationModeFanZA5 as FanZA5OperationMode,
)
import voluptuous as vol

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import ATTR_ENTITY_ID, CONF_DEVICE, CONF_MODEL
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import (
    CONF_FLOW_TYPE,
    DOMAIN,
    FEATURE_FLAGS_AIRFRESH,
    FEATURE_FLAGS_AIRFRESH_A1,
    FEATURE_FLAGS_AIRFRESH_T2017,
    FEATURE_FLAGS_AIRPURIFIER_2S,
    FEATURE_FLAGS_AIRPURIFIER_3C,
    FEATURE_FLAGS_AIRPURIFIER_4,
    FEATURE_FLAGS_AIRPURIFIER_4_LITE,
    FEATURE_FLAGS_AIRPURIFIER_MIIO,
    FEATURE_FLAGS_AIRPURIFIER_MIOT,
    FEATURE_FLAGS_AIRPURIFIER_PRO,
    FEATURE_FLAGS_AIRPURIFIER_PRO_V7,
    FEATURE_FLAGS_AIRPURIFIER_V3,
    FEATURE_FLAGS_AIRPURIFIER_ZA1,
    FEATURE_FLAGS_FAN,
    FEATURE_FLAGS_FAN_1C,
    FEATURE_FLAGS_FAN_P5,
    FEATURE_FLAGS_FAN_P9,
    FEATURE_FLAGS_FAN_P10_P11_P18,
    FEATURE_FLAGS_FAN_ZA5,
    FEATURE_RESET_FILTER,
    FEATURE_SET_EXTRA_FEATURES,
    MODEL_AIRFRESH_A1,
    MODEL_AIRFRESH_T2017,
    MODEL_AIRPURIFIER_2H,
    MODEL_AIRPURIFIER_2S,
    MODEL_AIRPURIFIER_3C,
    MODEL_AIRPURIFIER_3C_REV_A,
    MODEL_AIRPURIFIER_4,
    MODEL_AIRPURIFIER_4_LITE_RMA1,
    MODEL_AIRPURIFIER_4_LITE_RMB1,
    MODEL_AIRPURIFIER_4_PRO,
    MODEL_AIRPURIFIER_PRO,
    MODEL_AIRPURIFIER_PRO_V7,
    MODEL_AIRPURIFIER_V3,
    MODEL_AIRPURIFIER_ZA1,
    MODEL_FAN_1C,
    MODEL_FAN_P5,
    MODEL_FAN_P9,
    MODEL_FAN_P10,
    MODEL_FAN_P11,
    MODEL_FAN_P18,
    MODEL_FAN_ZA5,
    MODELS_FAN_MIIO,
    MODELS_FAN_MIOT,
    MODELS_PURIFIER_MIOT,
    SERVICE_RESET_FILTER,
    SERVICE_SET_EXTRA_FEATURES,
)
from .entity import XiaomiCoordinatedMiioEntity
from .typing import ServiceMethodDetails, XiaomiMiioConfigEntry

_LOGGER = logging.getLogger(__name__)

DATA_KEY = "fan.xiaomi_miio"

ATTR_MODE_NATURE = "nature"
ATTR_MODE_NORMAL = "normal"

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

# Air Fresh A1
ATTR_FAVORITE_SPEED = "favorite_speed"

# Air Purifier 3C
ATTR_FAVORITE_RPM = "favorite_rpm"
ATTR_MOTOR_SPEED = "motor_speed"

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
PRESET_MODES_AIRPURIFIER_4_LITE = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_MIOT = ["Auto", "Silent", "Favorite", "Fan"]
PRESET_MODES_AIRPURIFIER_PRO = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_PRO_V7 = PRESET_MODES_AIRPURIFIER_PRO
PRESET_MODES_AIRPURIFIER_2S = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_3C = ["Auto", "Silent", "Favorite"]
PRESET_MODES_AIRPURIFIER_ZA1 = ["Auto", "Silent", "Favorite"]
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
PRESET_MODES_AIRFRESH_A1 = ["Auto", "Sleep", "Favorite"]

AIRPURIFIER_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})

SERVICE_SCHEMA_EXTRA_FEATURES = AIRPURIFIER_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_FEATURES): cv.positive_int}
)

SERVICE_TO_METHOD = {
    SERVICE_RESET_FILTER: ServiceMethodDetails(method="async_reset_filter"),
    SERVICE_SET_EXTRA_FEATURES: ServiceMethodDetails(
        method="async_set_extra_features",
        schema=SERVICE_SCHEMA_EXTRA_FEATURES,
    ),
}

FAN_DIRECTIONS_MAP = {
    "forward": "right",
    "reverse": "left",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: XiaomiMiioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Fan from a config entry."""
    entities: list[FanEntity] = []
    entity: FanEntity

    if config_entry.data[CONF_FLOW_TYPE] != CONF_DEVICE:
        return

    hass.data.setdefault(DATA_KEY, {})

    model = config_entry.data[CONF_MODEL]
    unique_id = config_entry.unique_id
    device = config_entry.runtime_data.device
    coordinator = config_entry.runtime_data.device_coordinator

    if model in (MODEL_AIRPURIFIER_3C, MODEL_AIRPURIFIER_3C_REV_A):
        entity = XiaomiAirPurifierMB4(
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    elif model in MODELS_PURIFIER_MIOT:
        entity = XiaomiAirPurifierMiot(
            device,
            config_entry,
            unique_id,
            coordinator,
        )
    elif model.startswith("zhimi.airpurifier."):
        entity = XiaomiAirPurifier(device, config_entry, unique_id, coordinator)
    elif model.startswith("zhimi.airfresh."):
        entity = XiaomiAirFresh(device, config_entry, unique_id, coordinator)
    elif model == MODEL_AIRFRESH_A1:
        entity = XiaomiAirFreshA1(device, config_entry, unique_id, coordinator)
    elif model == MODEL_AIRFRESH_T2017:
        entity = XiaomiAirFreshT2017(device, config_entry, unique_id, coordinator)
    elif model == MODEL_FAN_P5:
        entity = XiaomiFanP5(device, config_entry, unique_id, coordinator)
    elif model in MODELS_FAN_MIIO:
        entity = XiaomiFan(device, config_entry, unique_id, coordinator)
    elif model == MODEL_FAN_ZA5:
        entity = XiaomiFanZA5(device, config_entry, unique_id, coordinator)
    elif model == MODEL_FAN_1C:
        entity = XiaomiFan1C(device, config_entry, unique_id, coordinator)
    elif model in MODELS_FAN_MIOT:
        entity = XiaomiFanMiot(device, config_entry, unique_id, coordinator)
    else:
        return

    hass.data[DATA_KEY][unique_id] = entity

    entities.append(entity)

    async def async_service_handler(service: ServiceCall) -> None:
        """Map services to methods on XiaomiAirPurifier."""
        method = SERVICE_TO_METHOD[service.service]
        params = {
            key: value for key, value in service.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := service.data.get(ATTR_ENTITY_ID):
            filtered_entities = [
                entity
                for entity in hass.data[DATA_KEY].values()
                if entity.entity_id in entity_ids
            ]
        else:
            filtered_entities = hass.data[DATA_KEY].values()

        update_tasks = []

        for entity in filtered_entities:
            entity_method = getattr(entity, method.method, None)
            if not entity_method:
                continue
            await entity_method(**params)
            update_tasks.append(asyncio.create_task(entity.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for air_purifier_service, method in SERVICE_TO_METHOD.items():
        schema = method.schema or AIRPURIFIER_SERVICE_SCHEMA
        hass.services.async_register(
            DOMAIN, air_purifier_service, async_service_handler, schema=schema
        )

    async_add_entities(entities)


class XiaomiGenericDevice(
    XiaomiCoordinatedMiioEntity[DataUpdateCoordinator[Any]], FanEntity
):
    """Representation of a generic Xiaomi device."""

    _attr_name = None
    _attr_preset_modes: list[str]

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the generic Xiaomi device."""
        super().__init__(device, entry, unique_id, coordinator)

        self._available_attributes: dict[str, Any] = {}
        self._mode: str | None = None
        self._fan_level: int | None = None
        self._attr_extra_state_attributes = {}
        self._device_features = 0
        self._attr_preset_modes = []

    @property
    @abstractmethod
    def operation_mode_class(self):
        """Hold operation mode class."""

    @property
    def percentage(self) -> int | None:
        """Return the percentage based speed of the fan."""
        return None

    @property
    def is_on(self) -> bool | None:
        """Return true if device is on."""
        # Base FanEntity uses percentage to determine if the device is on.
        return self._attr_is_on

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        result = await self._try_command(
            "Turning the miio device on failed.",
            self._device.on,  # type: ignore[attr-defined]
        )

        # If operation mode was set the device must not be turned on.
        if percentage:
            await self.async_set_percentage(percentage)
        if preset_mode:
            await self.async_set_preset_mode(preset_mode)

        if result:
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        result = await self._try_command(
            "Turning the miio device off failed.",
            self._device.off,  # type: ignore[attr-defined]
        )

        if result:
            self._attr_is_on = False
            self.async_write_ha_state()


class XiaomiGenericAirPurifier(XiaomiGenericDevice):
    """Representation of a generic AirPurifier device."""

    @property
    def preset_mode(self) -> str | None:
        """Get the active preset mode."""
        if self._attr_is_on:
            preset_mode = self.operation_mode_class(self._mode).name
            return preset_mode if preset_mode in self._attr_preset_modes else None

        return None

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_extra_state_attributes.update(
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

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the plug switch."""
        super().__init__(device, entry, unique_id, coordinator)

        if self._model == MODEL_AIRPURIFIER_PRO:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_PRO
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        elif self._model in [MODEL_AIRPURIFIER_4, MODEL_AIRPURIFIER_4_PRO]:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_4
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_MIOT
            self._attr_supported_features = (
                FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
            )
            self._attr_speed_count = 3
        elif self._model in [
            MODEL_AIRPURIFIER_4_LITE_RMA1,
            MODEL_AIRPURIFIER_4_LITE_RMB1,
        ]:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_4_LITE
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_4_LITE
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        elif self._model == MODEL_AIRPURIFIER_PRO_V7:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_PRO_V7
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_PRO_V7
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_PRO_V7
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        elif self._model in [MODEL_AIRPURIFIER_2S, MODEL_AIRPURIFIER_2H]:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_2S
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_COMMON
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_2S
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        elif self._model == MODEL_AIRPURIFIER_ZA1:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_ZA1
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_ZA1
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        elif self._model in MODELS_PURIFIER_MIOT:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_MIOT
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_MIOT
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_MIOT
            self._attr_supported_features = (
                FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
            )
            self._attr_speed_count = 3
        elif self._model == MODEL_AIRPURIFIER_V3:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_V3
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER_V3
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_V3
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        else:
            self._device_features = FEATURE_FLAGS_AIRPURIFIER_MIIO
            self._available_attributes = AVAILABLE_ATTRIBUTES_AIRPURIFIER
            self._attr_preset_modes = PRESET_MODES_AIRPURIFIER
            self._attr_supported_features = FanEntityFeature.PRESET_MODE
            self._attr_speed_count = 1
        self._attr_supported_features |= (
            FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
        )

        self._attr_is_on = self.coordinator.data.is_on
        self._attr_extra_state_attributes.update(
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
    def percentage(self) -> int | None:
        """Return the current percentage based speed."""
        if self._attr_is_on:
            mode = self.operation_mode_class(self._mode)
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self.speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
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
            percentage_to_ranged_value((1, self.speed_count), percentage)
        )
        if speed_mode:
            await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,  # type: ignore[attr-defined]
                self.operation_mode_class(self.SPEED_MODE_MAPPING[speed_mode]),
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan.

        This method is a coroutine.
        """
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
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
            self._device.set_extra_features,  # type: ignore[attr-defined]
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
    def percentage(self) -> int | None:
        """Return the current percentage based speed."""
        if self._fan_level is None:
            return None
        if self._attr_is_on:
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
            self._device.set_fan_level,  # type: ignore[attr-defined]
            fan_level,
        ):
            self._fan_level = fan_level
            self.async_write_ha_state()


class XiaomiAirPurifierMB4(XiaomiGenericAirPurifier):
    """Representation of a Xiaomi Air Purifier MB4."""

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize Air Purifier MB4."""
        super().__init__(device, entry, unique_id, coordinator)

        self._device_features = FEATURE_FLAGS_AIRPURIFIER_3C
        self._attr_preset_modes = PRESET_MODES_AIRPURIFIER_3C
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

        self._attr_is_on = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value
        self._favorite_rpm: int | None = None
        self._speed_range = (300, 2200)
        self._motor_speed = 0

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirpurifierMiotOperationMode

    @property
    def percentage(self) -> int | None:
        """Return the current percentage based speed."""
        # show the actual fan speed in silent or auto preset mode
        if self._mode != self.operation_mode_class["Favorite"].value:
            return ranged_value_to_percentage(self._speed_range, self._motor_speed)
        if self._favorite_rpm is None:
            return None
        if self._attr_is_on:
            return ranged_value_to_percentage(self._speed_range, self._favorite_rpm)

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan. This method is a coroutine."""
        if percentage == 0:
            await self.async_turn_off()
            return

        favorite_rpm = int(
            round(percentage_to_ranged_value(self._speed_range, percentage), -1)
        )
        if not favorite_rpm:
            return
        if await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_favorite_rpm,  # type: ignore[attr-defined]
            favorite_rpm,
        ):
            self._favorite_rpm = favorite_rpm
            self._mode = self.operation_mode_class["Favorite"].value
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if not self._attr_is_on:
            await self.async_turn_on()

        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            self.operation_mode_class[preset_mode],
        ):
            self._mode = self.operation_mode_class[preset_mode].value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value
        self._favorite_rpm = getattr(self.coordinator.data, ATTR_FAVORITE_RPM, None)
        self._motor_speed = min(
            self._speed_range[1],
            max(
                self._speed_range[0],
                getattr(self.coordinator.data, ATTR_MOTOR_SPEED, 0),
            ),
        )
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

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the miio device."""
        super().__init__(device, entry, unique_id, coordinator)

        self._device_features = FEATURE_FLAGS_AIRFRESH
        self._available_attributes = AVAILABLE_ATTRIBUTES_AIRFRESH
        self._attr_speed_count = 4
        self._attr_preset_modes = PRESET_MODES_AIRFRESH
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

        self._attr_is_on = self.coordinator.data.is_on
        self._attr_extra_state_attributes.update(
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
    def percentage(self) -> int | None:
        """Return the current percentage based speed."""
        if self._attr_is_on:
            mode = AirfreshOperationMode(self._mode)
            if mode in self.REVERSE_SPEED_MODE_MAPPING:
                return ranged_value_to_percentage(
                    (1, self.speed_count), self.REVERSE_SPEED_MODE_MAPPING[mode]
                )

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan.

        This method is a coroutine.
        """
        speed_mode = math.ceil(
            percentage_to_ranged_value((1, self.speed_count), percentage)
        )
        if speed_mode:
            if await self._try_command(
                "Setting operation mode of the miio device failed.",
                self._device.set_mode,  # type: ignore[attr-defined]
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
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
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
            self._device.set_extra_features,  # type: ignore[attr-defined]
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


class XiaomiAirFreshA1(XiaomiGenericAirPurifier):
    """Representation of a Xiaomi Air Fresh A1."""

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the miio device."""
        super().__init__(device, entry, unique_id, coordinator)
        self._favorite_speed: int | None = None
        self._device_features = FEATURE_FLAGS_AIRFRESH_A1
        self._attr_preset_modes = PRESET_MODES_AIRFRESH_A1
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )

        self._attr_is_on = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value
        self._speed_range = (60, 150)

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return AirfreshOperationModeT2017

    @property
    def percentage(self) -> int | None:
        """Return the current percentage based speed."""
        if self._favorite_speed is None:
            return None
        if self._attr_is_on:
            return ranged_value_to_percentage(self._speed_range, self._favorite_speed)

        return None

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan. This method is a coroutine."""
        if percentage == 0:
            await self.async_turn_off()
            return

        await self.async_set_preset_mode("Favorite")

        favorite_speed = math.ceil(
            percentage_to_ranged_value(self._speed_range, percentage)
        )
        if not favorite_speed:
            return
        if await self._try_command(
            "Setting fan level of the miio device failed.",
            self._device.set_favorite_speed,  # type: ignore[attr-defined]
            favorite_speed,
        ):
            self._favorite_speed = favorite_speed
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan. This method is a coroutine."""
        if await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            self.operation_mode_class[preset_mode],
        ):
            self._mode = self.operation_mode_class[preset_mode].value
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._mode = self.coordinator.data.mode.value
        self._favorite_speed = getattr(self.coordinator.data, ATTR_FAVORITE_SPEED, None)
        self.async_write_ha_state()


class XiaomiAirFreshT2017(XiaomiAirFreshA1):
    """Representation of a Xiaomi Air Fresh T2017."""

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the miio device."""
        super().__init__(device, entry, unique_id, coordinator)
        self._device_features = FEATURE_FLAGS_AIRFRESH_T2017
        self._speed_range = (60, 300)


class XiaomiGenericFan(XiaomiGenericDevice):
    """Representation of a generic Xiaomi Fan."""

    _attr_translation_key = "generic_fan"

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the fan."""
        super().__init__(device, entry, unique_id, coordinator)

        if self._model == MODEL_FAN_P5:
            self._device_features = FEATURE_FLAGS_FAN_P5
        elif self._model == MODEL_FAN_ZA5:
            self._device_features = FEATURE_FLAGS_FAN_ZA5
        elif self._model == MODEL_FAN_1C:
            self._device_features = FEATURE_FLAGS_FAN_1C
        elif self._model == MODEL_FAN_P9:
            self._device_features = FEATURE_FLAGS_FAN_P9
        elif self._model in (MODEL_FAN_P10, MODEL_FAN_P11, MODEL_FAN_P18):
            self._device_features = FEATURE_FLAGS_FAN_P10_P11_P18
        else:
            self._device_features = FEATURE_FLAGS_FAN
        self._attr_supported_features = (
            FanEntityFeature.SET_SPEED
            | FanEntityFeature.OSCILLATE
            | FanEntityFeature.PRESET_MODE
            | FanEntityFeature.TURN_OFF
            | FanEntityFeature.TURN_ON
        )
        if self._model != MODEL_FAN_1C:
            self._attr_supported_features |= FanEntityFeature.DIRECTION
        self._percentage: int | None = None

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return [mode.name for mode in self.operation_mode_class]

    @property
    def percentage(self) -> int | None:
        """Return the current speed as a percentage."""
        if self._attr_is_on:
            return self._percentage

        return None

    async def async_oscillate(self, oscillating: bool) -> None:
        """Set oscillation."""
        await self._try_command(
            "Setting oscillate on/off of the miio device failed.",
            self._device.set_oscillate,  # type: ignore[attr-defined]
            oscillating,
        )
        self._attr_oscillating = oscillating
        self.async_write_ha_state()

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        if self._attr_oscillating:
            await self.async_oscillate(oscillating=False)

        await self._try_command(
            "Setting move direction of the miio device failed.",
            self._device.set_rotate,  # type: ignore[attr-defined]
            FanMoveDirection(FAN_DIRECTIONS_MAP[direction]),
        )


class XiaomiFan(XiaomiGenericFan):
    """Representation of a Xiaomi Fan."""

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize the fan."""
        super().__init__(device, entry, unique_id, coordinator)

        self._attr_is_on = self.coordinator.data.is_on
        self._attr_oscillating = self.coordinator.data.oscillate
        self._nature_mode = self.coordinator.data.natural_speed != 0
        if self._nature_mode:
            self._percentage = self.coordinator.data.natural_speed
        else:
            self._percentage = self.coordinator.data.direct_speed

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""

    @property
    def preset_mode(self) -> str:
        """Get the active preset mode."""
        return ATTR_MODE_NATURE if self._nature_mode else ATTR_MODE_NORMAL

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return [ATTR_MODE_NATURE, ATTR_MODE_NORMAL]

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_oscillating = self.coordinator.data.oscillate
        self._nature_mode = self.coordinator.data.natural_speed != 0
        if self._nature_mode:
            self._percentage = self.coordinator.data.natural_speed
        else:
            self._percentage = self.coordinator.data.direct_speed

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == ATTR_MODE_NATURE:
            await self._try_command(
                "Setting natural fan speed percentage of the miio device failed.",
                self._device.set_natural_speed,  # type: ignore[attr-defined]
                self._percentage,
            )
        else:
            await self._try_command(
                "Setting direct fan speed percentage of the miio device failed.",
                self._device.set_direct_speed,  # type: ignore[attr-defined]
                self._percentage,
            )

        self._attr_preset_mode = preset_mode
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
                self._device.set_natural_speed,  # type: ignore[attr-defined]
                percentage,
            )
        else:
            await self._try_command(
                "Setting fan speed percentage of the miio device failed.",
                self._device.set_direct_speed,  # type: ignore[attr-defined]
                percentage,
            )
        self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        else:
            self.async_write_ha_state()


class XiaomiFanP5(XiaomiGenericFan):
    """Representation of a Xiaomi Fan P5."""

    coordinator: DataUpdateCoordinator[FanStatusP5]

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[FanStatusP5],
    ) -> None:
        """Initialize the fan."""
        super().__init__(device, entry, unique_id, coordinator)

        self._attr_is_on = self.coordinator.data.is_on
        self._attr_preset_mode = self.coordinator.data.mode.name
        self._attr_oscillating = self.coordinator.data.oscillate
        self._percentage = self.coordinator.data.speed

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return FanOperationMode

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_preset_mode = self.coordinator.data.mode.name
        self._attr_oscillating = self.coordinator.data.oscillate
        self._percentage = self.coordinator.data.speed

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            self.operation_mode_class[preset_mode],
        )
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,  # type: ignore[attr-defined]
            percentage,
        )
        self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        else:
            self.async_write_ha_state()


class XiaomiFanMiot(XiaomiGenericFan):
    """Representation of a Xiaomi Fan Miot."""

    coordinator: DataUpdateCoordinator[FanStatusMiot]

    @property
    def operation_mode_class(self) -> type[FanOperationMode]:
        """Hold operation mode class."""
        return FanOperationMode

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_preset_mode = self.coordinator.data.mode.name
        self._attr_oscillating = self.coordinator.data.oscillate
        if self.coordinator.data.is_on:
            self._percentage = self.coordinator.data.speed
        else:
            self._percentage = 0

        self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        await self._try_command(
            "Setting operation mode of the miio device failed.",
            self._device.set_mode,  # type: ignore[attr-defined]
            self.operation_mode_class[preset_mode],
        )
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        result = await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,  # type: ignore[attr-defined]
            percentage,
        )
        if result:
            self._percentage = percentage

        if not self.is_on:
            await self.async_turn_on()
        elif result:
            self.async_write_ha_state()


class XiaomiFanZA5(XiaomiFanMiot):
    """Representation of a Xiaomi Fan ZA5."""

    @property
    def operation_mode_class(self):
        """Hold operation mode class."""
        return FanZA5OperationMode


class XiaomiFan1C(XiaomiFanMiot):
    """Representation of a Xiaomi Fan 1C (Standing Fan 2 Lite)."""

    def __init__(
        self,
        device: MiioDevice,
        entry: XiaomiMiioConfigEntry,
        unique_id: str | None,
        coordinator: DataUpdateCoordinator[Any],
    ) -> None:
        """Initialize MIOT fan with speed count."""
        super().__init__(device, entry, unique_id, coordinator)
        self._attr_speed_count = 3

    @callback
    def _handle_coordinator_update(self):
        """Fetch state from the device."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_preset_mode = self.coordinator.data.mode.name
        self._attr_oscillating = self.coordinator.data.oscillate
        if self.coordinator.data.is_on:
            self._percentage = ranged_value_to_percentage(
                (1, self.speed_count), self.coordinator.data.speed
            )
        else:
            self._percentage = 0

        self.async_write_ha_state()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the percentage of the fan."""
        if percentage == 0:
            self._percentage = 0
            await self.async_turn_off()
            return

        speed = math.ceil(percentage_to_ranged_value((1, self.speed_count), percentage))

        # if the fan is not on, we have to turn it on first
        if not self.is_on:
            await self.async_turn_on()

        result = await self._try_command(
            "Setting fan speed percentage of the miio device failed.",
            self._device.set_speed,  # type: ignore[attr-defined]
            speed,
        )

        if result:
            self._percentage = ranged_value_to_percentage((1, self.speed_count), speed)
            self.async_write_ha_state()
