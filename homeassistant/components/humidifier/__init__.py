"""Provides functionality to interact with humidifier devices."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_MODE,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    ATTR_MAX_HUMIDITY,
    ATTR_MIN_HUMIDITY,
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_DEHUMIDIFIER,
    DEVICE_CLASS_HUMIDIFIER,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    SUPPORT_MODES,
)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=60)

DEVICE_CLASSES = [DEVICE_CLASS_HUMIDIFIER, DEVICE_CLASS_DEHUMIDIFIER]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))


@bind_hass
def is_on(hass, entity_id):
    """Return if the humidifier is on based on the statemachine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up humidifier devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_TURN_ON, {}, "async_turn_on")
    component.async_register_entity_service(SERVICE_TURN_OFF, {}, "async_turn_off")
    component.async_register_entity_service(SERVICE_TOGGLE, {}, "async_toggle")
    component.async_register_entity_service(
        SERVICE_SET_MODE,
        {vol.Required(ATTR_MODE): cv.string},
        "async_set_mode",
        [SUPPORT_MODES],
    )
    component.async_register_entity_service(
        SERVICE_SET_HUMIDITY,
        {
            vol.Required(ATTR_HUMIDITY): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)
            )
        },
        "async_set_humidity",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class HumidifierEntity(ToggleEntity):
    """Base class for humidifier entities."""

    @property
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes."""
        supported_features = self.supported_features or 0
        data = {
            ATTR_MIN_HUMIDITY: self.min_humidity,
            ATTR_MAX_HUMIDITY: self.max_humidity,
        }

        if supported_features & SUPPORT_MODES:
            data[ATTR_AVAILABLE_MODES] = self.available_modes

        return data

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features or 0
        data = {}

        if self.target_humidity is not None:
            data[ATTR_HUMIDITY] = self.target_humidity

        if supported_features & SUPPORT_MODES:
            data[ATTR_MODE] = self.mode

        return data

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return None

    @property
    def mode(self) -> str | None:
        """Return the current mode, e.g., home, auto, baby.

        Requires SUPPORT_MODES.
        """
        raise NotImplementedError

    @property
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes.

        Requires SUPPORT_MODES.
        """
        raise NotImplementedError

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        raise NotImplementedError()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        await self.hass.async_add_executor_job(self.set_humidity, humidity)

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        raise NotImplementedError()

    async def async_set_mode(self, mode: str) -> None:
        """Set new mode."""
        await self.hass.async_add_executor_job(self.set_mode, mode)

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY
