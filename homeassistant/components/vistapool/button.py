"""Vistapool Button entities."""

import asyncio

from aioaquarite import AquariteError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_HASLED_PATH = "main.hasLED"
_LIGHT_STATUS_PATH = "light.status"
_LED_PULSE_DELAY_SECONDS = 1.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool buttons for every pool that has an LED fixture."""
    async_add_entities(
        VistapoolLEDPulseButton(coordinator)
        for coordinator in entry.runtime_data.coordinators.values()
        if coordinator.get_value(_HASLED_PATH)
    )


class VistapoolLEDPulseButton(VistapoolEntity, ButtonEntity):
    """Power-cycle the pool light to advance the LED fixture's color.

    Mirrors the "Next" button under LED Color in the Vistapool app's
    Illumination screen. If the light is on, sends light.status=0, waits a
    moment, then light.status=1; the physical LED fixture advances to the
    next color on power-on. If the light is off, just turns it on.
    """

    _attr_translation_key = "led_pulse"

    def __init__(self, coordinator: VistapoolDataUpdateCoordinator) -> None:
        """Initialize the LED pulse button."""
        super().__init__(coordinator)
        self._attr_unique_id = self.build_unique_id("led_pulse")

    async def async_press(self) -> None:
        """Send a color-advance pulse to the pool LED fixture."""
        try:
            if self.coordinator.get_value(_LIGHT_STATUS_PATH) in (True, "1"):
                await self.coordinator.api.set_value(
                    self.coordinator.pool_id, _LIGHT_STATUS_PATH, 0
                )
                await asyncio.sleep(_LED_PULSE_DELAY_SECONDS)
            await self.coordinator.api.set_value(
                self.coordinator.pool_id, _LIGHT_STATUS_PATH, 1
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
        # Optimistically reflect the just-written value so a rapid second press
        # doesn't read the stale off-state before the Firestore push round-trips.
        self.coordinator.data.setdefault("light", {})["status"] = 1
        self.coordinator.async_set_updated_data(self.coordinator.data)
