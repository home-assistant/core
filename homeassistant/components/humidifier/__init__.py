"""Provides functionality to interact with humidifier devices."""
from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON, STATE_OFF, STATE_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    make_entity_service_schema,
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType, ServiceDataType

from .const import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HUMIDIFIER_ACTION,
    ATTR_OPERATION_MODE,
    ATTR_OPERATION_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    ATTR_WATER_LEVEL,
    DOMAIN,
    OPERATION_MODE_HUMIDIFY,
    OPERATION_MODE_DRY,
    OPERATION_MODE_HUMIDIFY_DRY,
    OPERATION_MODE_OFF,
    OPERATION_MODES,
    SERVICE_SET_AUX_HEAT,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_PRESET_MODE,
    SUPPORT_AUX_HEAT,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TEMPERATURE,
    SUPPORT_WATER_LEVEL,
    DEFAULT_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up humidifier devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(
        SERVICE_SET_FAN_MODE,
        make_entity_service_schema({vol.Required(ATTR_FAN_MODE): cv.string}),
        "async_set_fan_mode",
        [SUPPORT_FAN_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_OPERATION_MODE,
        make_entity_service_schema(
            {vol.Required(ATTR_OPERATION_MODE): vol.In(OPERATION_MODES)}
        ),
        "async_set_operation_mode",
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        make_entity_service_schema({vol.Required(ATTR_PRESET_MODE): cv.string}),
        "async_set_preset_mode",
        [SUPPORT_PRESET_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_AUX_HEAT,
        make_entity_service_schema({vol.Required(ATTR_AUX_HEAT): cv.boolean}),
        async_service_aux_heat,
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        make_entity_service_schema({vol.Required(ATTR_HUMIDITY): vol.Coerce(int)}),
        "async_set_humidity",
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class HumidifierDevice(Entity):
    """Representation of a humidifier device."""

    @property
    def state(self) -> str:
        """Return the current state."""
        return self.operation_mode

    @property
    def capability_attributes(self):
        """Return capability attributes."""
        data = {}
        supported_features = self.supported_features

        data[ATTR_MIN_HUMIDITY] = self.min_humidity
        data[ATTR_MAX_HUMIDITY] = self.max_humidity
        data[ATTR_OPERATION_MODES] = self.operation_modes

        if supported_features & SUPPORT_FAN_MODE:
            data[ATTR_FAN_MODES] = self.fan_modes

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODES] = self.preset_modes

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        data = {}
        supported_features = self.supported_features

        data[ATTR_HUMIDITY] = self.target_humidity
        data[ATTR_CURRENT_HUMIDITY] = self.current_humidity

        if supported_features & SUPPORT_FAN_MODE:
            data[ATTR_FAN_MODE] = self.fan_mode

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode

        if supported_features & SUPPORT_TEMPERATURE:
            data[ATTR_CURRENT_TEMPERATURE] = self.current_temperature

        if self.humidifier_action:
            data[ATTR_HUMIDIFIER_ACTION] = self.humidifier_action

        if supported_features & SUPPORT_WATER_LEVEL:
            data[ATTR_WATER_LEVEL] = self.water_level

        if supported_features & SUPPORT_AUX_HEAT:
            data[ATTR_AUX_HEAT] = STATE_ON if self.is_aux_heat else STATE_OFF

        return data

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return None

    @property
    def target_humidity(self) -> Optional[int]:
        """Return the humidity we try to reach."""
        return None

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement used by the platform."""
        raise NotImplementedError()

    @property
    def water_level(self) -> Optional[int]:
        """Return the water level."""
        return None

    @property
    def fan_mode(self) -> Optional[str]:
        """Return the fan setting.

        Requires SUPPORT_FAN_MODE.
        """
        raise NotImplementedError

    @property
    def fan_modes(self) -> Optional[List[str]]:
        """Return the list of available fan modes.

        Requires SUPPORT_FAN_MODE.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def operation_mode(self) -> str:
        """Return humidifier operation ie. humidify, dry mode.

        Need to be one of OPERATION_MODE_*.
        """

    @property
    @abstractmethod
    def operation_modes(self) -> List[str]:
        """Return the list of available humidifier operation modes.

        Need to be a subset of OPERATION_MODES.
        """

    @property
    def humidifier_action(self) -> Optional[str]:
        """Return the current running humidifier operation if supported.

        Need to be one of CURRENT_HUMIDIFIER_*.
        """
        return None

    @property
    def preset_mode(self) -> Optional[str]:
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        raise NotImplementedError

    @property
    def preset_modes(self) -> Optional[List[str]]:
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        raise NotImplementedError

    @property
    def is_aux_heat(self) -> Optional[bool]:
        """Return true if aux heater.

        Requires SUPPORT_AUX_HEAT.
        """
        raise NotImplementedError

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        raise NotImplementedError()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set new target operation mode."""
        await self.hass.async_add_executor_job(self.set_operation_mode, operation_mode)

    def set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        raise NotImplementedError()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        await self.hass.async_add_executor_job(self.set_fan_mode, fan_mode)

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        if hasattr(self, "turn_on"):
            # pylint: disable=no-member
            await self.hass.async_add_executor_job(self.turn_on)
            return

        # Fake turn on
        for mode in (
            OPERATION_MODE_HUMIDIFY_DRY,
            OPERATION_MODE_HUMIDIFY,
            OPERATION_MODE_DRY,
        ):
            if mode not in self.operation_modes:
                continue
            await self.async_set_operation_mode(mode)
            break

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if hasattr(self, "turn_off"):
            # pylint: disable=no-member
            await self.hass.async_add_executor_job(self.turn_off)
            return

        # Fake turn off
        if OPERATION_MODE_OFF in self.operation_modes:
            await self.async_set_operation_mode(OPERATION_MODE_OFF)

    @property
    @abstractmethod
    def supported_features(self) -> int:
        """Return the list of supported features."""

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY


async def async_service_aux_heat(
    entity: HumidifierDevice, service: ServiceDataType
) -> None:
    """Handle aux heat service."""
    if service.data[ATTR_AUX_HEAT]:
        await entity.async_turn_aux_heat_on()
    else:
        await entity.async_turn_aux_heat_off()
