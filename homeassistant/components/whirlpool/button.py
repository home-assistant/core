"""Button platform for the Whirlpool Appliances integration."""

from typing import override

from whirlpool.oven import Cavity as OvenCavity, Oven

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WhirlpoolConfigEntry
from .entity import WhirlpoolOvenEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WhirlpoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform."""
    appliances_manager = config_entry.runtime_data
    async_add_entities(
        WhirlpoolOvenStopButton(oven, cavity)
        for oven in appliances_manager.ovens
        for cavity in (OvenCavity.Upper, OvenCavity.Lower)
        if oven.get_oven_cavity_exists(cavity)
    )


class WhirlpoolOvenStopButton(WhirlpoolOvenEntity, ButtonEntity):
    """Button to stop the current cook in an oven cavity."""

    _appliance: Oven

    def __init__(self, appliance: Oven, cavity: OvenCavity) -> None:
        """Initialize the oven stop button."""
        super().__init__(appliance, cavity, "oven_stop", "-stop")

    @override
    async def async_press(self) -> None:
        """Stop cooking."""
        WhirlpoolOvenStopButton._check_service_request(
            await self._appliance.stop_cook(self.cavity)
        )
