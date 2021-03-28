"""Platform for switch integration."""
import logging

import async_timeout
from smarttub import SpaPump

from homeassistant.components.switch import SwitchEntity

from .const import API_TIMEOUT, ATTR_PUMPS, DOMAIN, SMARTTUB_CONTROLLER
from .entity import SmartTubEntity
from .helpers import get_spa_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switch entities for the pumps on the tub."""

    controller = hass.data[DOMAIN][entry.entry_id][SMARTTUB_CONTROLLER]

    entities = [
        SmartTubPump(controller.coordinator, pump)
        for spa in controller.spas
        for pump in controller.coordinator.data[spa.id][ATTR_PUMPS].values()
    ]

    async_add_entities(entities)


class SmartTubPump(SmartTubEntity, SwitchEntity):
    """A pump on a spa."""

    def __init__(self, coordinator, pump: SpaPump):
        """Initialize the entity."""
        super().__init__(coordinator, pump.spa, "pump")
        self.pump_id = pump.id
        self.pump_type = pump.type

    @property
    def pump(self) -> SpaPump:
        """Return the underlying SpaPump object for this entity."""
        return self.coordinator.data[self.spa.id]["pumps"][self.pump_id]

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this pump entity."""
        return f"{super().unique_id}-{self.pump_id}"

    @property
    def name(self) -> str:
        """Return a name for this pump entity."""
        spa_name = get_spa_name(self.spa)
        if self.pump_type == SpaPump.PumpType.CIRCULATION:
            return f"{spa_name} Circulation Pump"
        if self.pump_type == SpaPump.PumpType.JET:
            return f"{spa_name} Jet {self.pump_id}"
        return f"{spa_name} pump {self.pump_id}"

    @property
    def is_on(self) -> bool:
        """Return True if the pump is on."""
        return self.pump.state != SpaPump.PumpState.OFF

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the pump on."""

        # the API only supports toggling
        if not self.is_on:
            await self.async_toggle()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the pump off."""

        # the API only supports toggling
        if self.is_on:
            await self.async_toggle()

    async def async_toggle(self, **kwargs) -> None:
        """Toggle the pump on or off."""
        async with async_timeout.timeout(API_TIMEOUT):
            await self.pump.toggle()
        await self.coordinator.async_request_refresh()
