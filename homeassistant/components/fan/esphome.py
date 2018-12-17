"""Support for ESPHome fans."""
import logging
from typing import List, Optional, TYPE_CHECKING

from homeassistant.components.esphome import EsphomeEntity, \
    platform_async_setup_entry
from homeassistant.components.fan import FanEntity, SPEED_HIGH, SPEED_LOW, \
    SPEED_MEDIUM, SUPPORT_OSCILLATE, SUPPORT_SET_SPEED, SPEED_OFF
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType

if TYPE_CHECKING:
    # pylint: disable=unused-import
    from aioesphomeapi import FanInfo, FanState  # noqa

DEPENDENCIES = ['esphome']
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType,
                            entry: ConfigEntry, async_add_entities) -> None:
    """Set up ESPHome fans based on a config entry."""
    # pylint: disable=redefined-outer-name
    from aioesphomeapi import FanInfo, FanState  # noqa

    await platform_async_setup_entry(
        hass, entry, async_add_entities,
        component_key='fan',
        info_type=FanInfo, entity_type=EsphomeFan,
        state_type=FanState
    )


FAN_SPEED_STR_TO_INT = {
    SPEED_LOW: 0,
    SPEED_MEDIUM: 1,
    SPEED_HIGH: 2
}
FAN_SPEED_INT_TO_STR = {v: k for k, v in FAN_SPEED_STR_TO_INT.items()}


class EsphomeFan(EsphomeEntity, FanEntity):
    """A fan implementation for ESPHome."""

    @property
    def _static_info(self) -> 'FanInfo':
        return super()._static_info

    @property
    def _state(self) -> Optional['FanState']:
        return super()._state

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
            return
        await self._client.fan_command(
            self._static_info.key, speed=FAN_SPEED_STR_TO_INT[speed])

    async def async_turn_on(self, speed: Optional[str] = None,
                            **kwargs) -> None:
        """Turn on the fan."""
        if speed == SPEED_OFF:
            await self.async_turn_off()
            return
        data = {'key': self._static_info.key, 'state': True}
        if speed is not None:
            data['speed'] = FAN_SPEED_STR_TO_INT[speed]
        await self._client.fan_command(**data)

    # pylint: disable=arguments-differ
    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the fan."""
        await self._client.fan_command(key=self._static_info.key, state=False)

    async def async_oscillate(self, oscillating: bool):
        """Oscillate the fan."""
        await self._client.fan_command(key=self._static_info.key,
                                       oscillating=oscillating)

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the entity is on."""
        if self._state is None:
            return None
        return self._state.state

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if self._state is None:
            return None
        return FAN_SPEED_INT_TO_STR[self._state.speed]

    @property
    def oscillating(self) -> None:
        """Return the oscillation state."""
        if self._state is None:
            return None
        return self._state.oscillating

    @property
    def speed_list(self) -> List[str]:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = 0
        if self._static_info.supports_oscillation:
            flags |= SUPPORT_OSCILLATE
        if self._static_info.supports_speed:
            flags |= SUPPORT_SET_SPEED
        return flags
