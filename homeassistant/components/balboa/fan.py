"""Support for Balboa Spa Pumps."""
import logging

from homeassistant.components.fan import (
    SPEED_LOW,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.const import CONF_NAME

from . import BalboaEntity
from .const import DOMAIN as BALBOA_DOMAIN, FAN_SUPPORTED_SPEEDS

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up of the spa is done through async_setup_entry."""
    pass


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the spa's pumps as FAN entities."""
    spa = hass.data[BALBOA_DOMAIN][entry.entry_id]
    name = entry.data[CONF_NAME]
    devs = []

    pumps = spa.get_pump_list()

    for idx in enumerate(pumps):
        if pumps[idx[0]]:
            devs.append(BalboaSpaPump(hass, spa, f"{name}-pump{idx[0] + 1}", idx[0]))

    async_add_entities(devs, True)


class BalboaSpaPump(BalboaEntity, FanEntity):
    """Representation of a Balboa Spa pump device."""

    def __init__(self, hass, client, name, pump):
        """Initialize the pump."""
        super().__init__(hass, client, name)
        self.pump = pump
        _LOGGER.debug("Creating pump #%d", pump)

    async def async_set_speed(self, speed: str) -> None:
        """Set speed of pump."""
        setto = FAN_SUPPORTED_SPEEDS.index(speed)
        _LOGGER.debug("set pump %d to speed %d (%s)", self.pump, setto, speed)
        await self._client.change_pump(self.pump, setto)

    async def async_turn_on(self, speed: str = None, **kwargs) -> None:
        """Turn on pump."""
        if speed is None:
            speed = SPEED_LOW
        await self.async_set_speed(speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off pump."""
        await self.async_set_speed(SPEED_OFF)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return FAN_SUPPORTED_SPEEDS

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_SET_SPEED

    @property
    def speed(self) -> str:
        """Return the current speed."""
        pstate = self._client.get_pump(self.pump)
        _LOGGER.debug("speed %s state = %d pump = %d", self._name, pstate, self.pump)
        if pstate >= len(FAN_SUPPORTED_SPEEDS) or pstate < 0:
            return SPEED_OFF
        return FAN_SUPPORTED_SPEEDS[pstate]

    @property
    def is_on(self):
        """Return true if the pump is on."""
        pstate = self._client.get_pump(self.pump)
        return bool(pstate)

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:water-pump"
