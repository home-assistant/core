"""Support for Z-Wave fans."""
import logging
import math
from typing import Any, Callable, List, Optional

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = SUPPORT_SET_SPEED

# Value will first be divided to an integer
VALUE_TO_SPEED = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 3: SPEED_HIGH}
SPEED_TO_VALUE = {SPEED_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 50, SPEED_HIGH: 99}
SPEED_LIST = [*SPEED_TO_VALUE]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Fan from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_fan(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave fan."""
        entities: List[ZWaveBaseEntity] = []
        entities.append(ZwaveFan(config_entry, client, info))
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{FAN_DOMAIN}",
            async_add_fan,
        )
    )


class ZwaveFan(ZWaveBaseEntity, FanEntity):
    """Representation of a Z-Wave fan."""

    def __init__(
        self, config_entry: ConfigEntry, client: ZwaveClient, info: ZwaveDiscoveryInfo
    ) -> None:
        """Initialize the fan."""
        super().__init__(config_entry, client, info)
        self._previous_speed: Optional[str] = None

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        if speed not in SPEED_TO_VALUE:
            raise ValueError(f"Invalid speed received: {speed}")
        self._previous_speed = speed
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, SPEED_TO_VALUE[speed])

    #
    # The fan entity model has changed to use percentages and preset_modes
    # instead of speeds.
    #
    # Please review
    # https://developers.home-assistant.io/docs/core/entity/fan/
    #
    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if speed is None:
            # Value 255 tells device to return to previous value
            target_value = self.get_zwave_value("targetValue")
            await self.info.node.async_set_value(target_value, 255)
        else:
            await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 0)

    @property
    def is_on(self) -> bool:
        """Return true if device is on (speed above 0)."""
        return bool(self.info.primary_value.value > 0)

    @property
    def speed(self) -> Optional[str]:
        """Return the current speed.

        The Z-Wave speed value is a byte 0-255. 255 means previous value.
        The normal range of the speed is 0-99. 0 means off.
        """
        value = math.ceil(self.info.primary_value.value * 3 / 100)
        return VALUE_TO_SPEED.get(value, self._previous_speed)

    @property
    def speed_list(self) -> List[str]:
        """Get the list of available speeds."""
        return SPEED_LIST

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORTED_FEATURES
