"""Provides functionality to interact with humidifier devices."""
from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_PRESET_MODE,
    SUPPORT_PRESET_MODE,
)

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


@bind_hass
def is_on(hass, entity_id):
    """Return if the humidifier is on based on the statemachine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up humidifier devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(
        SERVICE_SET_PRESET_MODE,
        make_entity_service_schema({vol.Required(ATTR_PRESET_MODE): cv.string}),
        "async_set_preset_mode",
        [SUPPORT_PRESET_MODE],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        make_entity_service_schema({vol.Required(ATTR_HUMIDITY): vol.Coerce(int)}),
        "async_set_humidity",
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class HumidifierEntity(ToggleEntity):
    """Representation of a humidifier device."""

    @property
    def precision(self) -> float:
        """Return the precision of the system."""
        if self.hass.config.units.temperature_unit == TEMP_CELSIUS:
            return PRECISION_TENTHS
        return PRECISION_WHOLE

    @property
    def capability_attributes(self) -> Dict[str, Any]:
        """Return capability attributes."""
        supported_features = self.supported_features
        data = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
        }

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODES] = self.preset_modes

        return data

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features
        data = {
            ATTR_HUMIDITY: self.target_humidity,
            ATTR_CURRENT_HUMIDITY: self.current_humidity,
        }

        if supported_features & SUPPORT_PRESET_MODE:
            data[ATTR_PRESET_MODE] = self.preset_mode

        if self.current_temperature is not None:
            data[ATTR_CURRENT_TEMPERATURE] = show_temp(
                self.hass,
                self.current_temperature,
                self.temperature_unit,
                self.precision,
            )

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

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        raise NotImplementedError()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        await self.hass.async_add_executor_job(self.set_preset_mode, preset_mode)

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
