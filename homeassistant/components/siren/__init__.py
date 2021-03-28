"""Component to interface with various sirens/chimes."""
from datetime import timedelta
import logging
from typing import Any, Dict, List, Optional, Union

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

from .const import (
    ATTR_ACTIVE_TONE,
    ATTR_AVAILABLE_TONES,
    ATTR_DURATION,
    ATTR_TONE,
    ATTR_VOLUME_LEVEL,
    DOMAIN,
    SERVICE_SET_ACTIVE_TONE,
    SERVICE_SET_DURATION,
    SERVICE_SET_VOLUME_LEVEL,
    SUPPORT_DURATION,
    SUPPORT_TONES,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

TONE_SCHEMA = {vol.Optional(ATTR_TONE): cv.string}


@bind_hass
def is_on(hass, entity_id):
    """
    Return if the siren is on based on the state machine.

    Async friendly.
    """
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up siren devices."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON, TONE_SCHEMA, "async_turn_on", [SUPPORT_TURN_ON]
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF, {}, "async_turn_off", [SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE, {}, "async_toggle", [SUPPORT_TURN_ON & SUPPORT_TURN_OFF]
    )
    component.async_register_entity_service(
        SERVICE_SET_ACTIVE_TONE,
        TONE_SCHEMA,
        "async_set_active_tone",
        [SUPPORT_TONES],
    )
    component.async_register_entity_service(
        SERVICE_SET_DURATION,
        TONE_SCHEMA,
        "async_set_duration",
        [SUPPORT_DURATION],
    )
    component.async_register_entity_service(
        SERVICE_SET_VOLUME_LEVEL,
        {vol.Required(ATTR_VOLUME_LEVEL): vol.Coerce(float)},
        "async_set_volume_level",
        [SUPPORT_VOLUME_SET],
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class SirenEntity(ToggleEntity):
    """Representation of a siren device."""

    @property
    def capability_attributes(self) -> Optional[Dict[str, Any]]:
        """Return capability attributes."""
        supported_features = self.supported_features or 0

        if supported_features & SUPPORT_TONES:
            return {ATTR_AVAILABLE_TONES: self.available_tones}

        return None

    @property
    def state_attributes(self) -> Dict[str, Any]:
        """Return the optional state attributes."""
        supported_features = self.supported_features or 0
        data = {}

        if self.volume_level is not None:
            data[ATTR_VOLUME_LEVEL] = self.volume_level

        if supported_features & SUPPORT_TONES:
            data[ATTR_ACTIVE_TONE] = self.active_tone

        if supported_features & SUPPORT_DURATION:
            data[ATTR_DURATION] = self.duration

        return data

    @property
    def volume_level(self) -> Optional[float]:
        """Return the volume level of the device (0 - 1)."""
        return None

    @property
    def duration(self) -> Optional[int]:
        """Return the duration in seconds of the noise."""
        return None

    @property
    def active_tone(self) -> Optional[Union[int, str]]:
        """
        Return the active tone for the siren.

        Requires SUPPORT_TONES.
        """
        raise NotImplementedError

    @property
    def available_tones(self) -> Optional[Union[List[int], List[str]]]:
        """
        Return a list of available tones.

        Requires SUPPORT_TONES.
        """
        raise NotImplementedError

    def set_active_tone(self, tone: Union[int, str]) -> None:
        """Set new active tone."""
        raise NotImplementedError()

    async def async_set_active_tone(self, tone: Union[int, str]) -> None:
        """Set new active tone."""
        await self.hass.async_add_executor_job(self.set_active_tone, tone)

    def set_volume_level(self, volume_level: float) -> None:
        """Set volume level."""
        raise NotImplementedError()

    async def async_set_volume_level(self, volume_level: float) -> None:
        """Set volume level."""
        await self.hass.async_add_executor_job(self.set_volume_level, volume_level)

    def set_duration(self, duration: int) -> None:
        """Set siren duration in seconds."""
        raise NotImplementedError()

    async def async_set_duration(self, duration: int) -> None:
        """Set siren duration in seconds."""
        await self.hass.async_add_executor_job(self.set_duration, duration)
