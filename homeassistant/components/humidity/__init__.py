"""Provides functionality to interact with humidity devices."""
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa
    ENTITY_SERVICE_SCHEMA,
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HUMIDIFIER_ACTIONS,
    ATTR_HUMIDIFIER_MODE,
    ATTR_HUMIDIFIER_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN,
    HUMIDIFIER_MODE_HUMIDIFY,
    HUMIDIFIER_MODE_DRY,
    HUMIDIFIER_MODE_HUMIDIFY_DRY,
    HUMIDIFIER_MODE_OFF,
    HUMIDIFIER_MODES,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_HUMIDIFIER_MODE,
    SERVICE_SET_PRESET_MODE,
    SUPPORT_FAN_MODE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_HUMIDITY,
)

DEFAULT_MIN_HUMIDITY = 30
DEFAULT_MAX_HUMIDITY = 99

ENTITY_ID_FORMAT = DOMAIN + ".{}"
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)

SET_FAN_MODE_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_FAN_MODE): cv.string}
)
SET_PRESET_MODE_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_PRESET_MODE): cv.string}
)
SET_HUMIDIFIER_MODE_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_HUMIDIFIER_MODE): vol.In(HUMIDIFIER_MODES)}
)
SET_HUMIDITY_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_HUMIDITY): vol.Coerce(float)}
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up humidity devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, ENTITY_SERVICE_SCHEMA, "async_turn_on"
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, ENTITY_SERVICE_SCHEMA, "async_turn_off"
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_MODE, SET_FAN_MODE_SCHEMA, "async_set_fan_mode"
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDIFIER_MODE,
        SET_HUMIDIFIER_MODE_SCHEMA,
        "async_set_humidifier_mode",
    )
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE, SET_PRESET_MODE_SCHEMA, "async_set_preset_mode"
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY, SET_HUMIDITY_SCHEMA, "async_set_humidity"
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class HumidityDevice(Entity):
    """Representation of a humidity device."""

    @property
    def state(self) -> str:
        """Return the current state."""
        return self.humidifier_mode

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        data = {
            ATTR_HUMIDIFIER_MODES: self.humidifier_modes,
            ATTR_CURRENT_HUMIDITY: self.current_humidity,
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
        }

        if supported_features & SUPPORT_TARGET_HUMIDITY:
            data[ATTR_HUMIDITY] = self.target_humidity
            data[ATTR_MIN_HUMIDITY] = self.min_humidity
            data[ATTR_MAX_HUMIDITY] = self.max_humidity

        if self.humidifier_action:
            data[ATTR_HUMIDIFIER_ACTIONS] = self.humidifier_action

        if supported_features & SUPPORT_FAN_MODE:
            data[ATTR_FAN_MODE] = self.fan_mode
            data[ATTR_FAN_MODES] = self.fan_modes

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode
            data[ATTR_PRESET_MODES] = self.preset_modes

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
    def humidifier_mode(self) -> str:
        """Return humidifier operation ie. humidify, dry mode.

        Need to be one of HUMIDIFIER_MODE_*.
        """
        raise NotImplementedError()

    @property
    def humidifier_modes(self) -> List[str]:
        """Return the list of available humidifier operation modes.

        Need to be a subset of HUMIDIFIER_MODES.
        """
        raise NotImplementedError()

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

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_humidifier_mode(self, humidifier_mode: str) -> None:
        """Set new target humidifier mode."""
        raise NotImplementedError()

    async def async_set_humidifier_mode(self, humidifier_mode: str) -> None:
        """Set new target humidifier mode."""
        await self.hass.async_add_executor_job(
            self.set_humidifier_mode, humidifier_mode
        )

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
            HUMIDIFIER_MODE_HUMIDIFY_DRY,
            HUMIDIFIER_MODE_HUMIDIFY,
            HUMIDIFIER_MODE_DRY,
        ):
            if mode not in self.humidifier_modes:
                continue
            await self.async_set_humidifier_mode(mode)
            break

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        if hasattr(self, "turn_off"):
            # pylint: disable=no-member
            await self.hass.async_add_executor_job(self.turn_off)
            return

        # Fake turn off
        if HUMIDIFIER_MODE_OFF in self.humidifier_modes:
            await self.async_set_humidifier_mode(HUMIDIFIER_MODE_OFF)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        raise NotImplementedError()

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY
