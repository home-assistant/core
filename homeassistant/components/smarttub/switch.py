"""Platform for switch integration."""
import logging

from smarttub import SpaPump

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switch entities for the pumps on the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubPump(controller.coordinator, pump)
        for spa in controller.spas
        for pump in await spa.get_pumps()
    ]

    async_add_entities(entities)


class SmartTubPump(SmartTubEntity, SwitchEntity):
    """A pump on a spa."""

    def __init__(self, coordinator, pump: SpaPump):
        """Initialize the entity."""
        super().__init__(coordinator, pump.spa, "pump")
        self.pump = pump

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this pump entity."""
        return super().unique_id + "-{pump.id}"

    @property
    def name(self) -> str:
        """Return a name for this pump entity."""
        spa_name = get_spa_name(self.spa)
        if self.pump.type == SpaPump.PumpType.CIRCULATION:
            return f"{spa_name} circulation pump"
        if self.pump.type == SpaPump.PumpType.JET:
            return f"{spa_name} jet {self.pump.id}"
        return f"{spa_name} pump {self.pump.id}"

    def update_pump(self, pump: SpaPump) -> None:
        """Update the SpaPump object with new state."""
        self.pump = pump

    @property
    def is_on(self) -> bool:
        """Return True if the pump is on."""
        return self.pump.state != SpaPump.PumpState.OFF

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the pump on."""
        if not self.is_on:
            await self.toggle()

    async def turn_off(self, **kwargs) -> None:
        """Turn the pump off."""
        if self.is_on:
            await self.toggle()

    async def toggle(self) -> None:
        """Toggle the pump on or off."""
        await self.pump.toggle()
