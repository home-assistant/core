"""Component to interface with analog switches that can be controlled remotely."""
from datetime import timedelta
import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant.const import (
    ATTR_MODE,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    DEVICE_CLASS_BRIGHTNESS,
    DEVICE_CLASS_LEVEL,
    DEVICE_CLASS_SPEED,
    DEVICE_CLASS_STRENGTH,
    DEVICE_CLASS_VOLUME,
    DOMAIN,
    MODE_SLIDER,
    SERVICE_DECREMENT,
    SERVICE_INCREMENT,
    SERVICE_SET_VALUE,
)

SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

DEVICE_CLASSES = [
    DEVICE_CLASS_VOLUME,
    DEVICE_CLASS_BRIGHTNESS,
    DEVICE_CLASS_SPEED,
    DEVICE_CLASS_STRENGTH,
    DEVICE_CLASS_LEVEL,
]

DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.In(DEVICE_CLASSES))

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Track states and offer events for switches."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(SERVICE_DECREMENT, {}, "async_decrement")
    component.async_register_entity_service(SERVICE_INCREMENT, {}, "async_increment")
    component.async_register_entity_service(
        SERVICE_SET_VALUE,
        {vol.Required(ATTR_VALUE): vol.Coerce(float)},
        "async_set_value",
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class AnalogSwitchEntity(Entity):
    """Representation of an analog switch."""

    @property
    def capability_attributes(self) -> Dict[str, Any]:
        """Return capability attributes."""
        data = {
            ATTR_MIN: self.min_value,
            ATTR_MAX: self.max_value,
            ATTR_STEP: self.step,
            ATTR_MODE: self.mode,
        }
        return data

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return DEFAULT_MIN_VALUE

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return DEFAULT_MAX_VALUE

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        step = DEFAULT_STEP
        value_range = abs(self.max_value - self.min_value)
        if value_range != 0:
            while value_range <= step:
                step /= 10.0
        return step

    @property
    def mode(self) -> float:
        """Return the appearance mode of the analog switch."""
        return MODE_SLIDER

    def set_value(self, value: float) -> None:
        """Set new value."""
        raise NotImplementedError()

    async def async_set_value(self, value: float) -> None:
        """Set new value."""
        await self.hass.async_add_executor_job(self.set_value, value)

    def increment(self) -> None:
        """Increment value."""
        self.set_value(min(float(self.state) + self.step, self.max_value))

    async def async_increment(self) -> None:
        """Increment value."""
        await self.async_set_value(min(float(self.state) + self.step, self.max_value))

    def decrement(self) -> None:
        """Decrement value."""
        self.set_value(max(float(self.state) - self.step, self.min_value))

    async def async_decrement(self) -> None:
        """Decrement value."""
        await self.async_set_value(max(float(self.state) - self.step, self.min_value))
