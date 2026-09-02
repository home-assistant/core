"""Vistapool Button entities."""

import asyncio
from typing import override

from aioaquarite import AquariteError

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VistapoolConfigEntry
from .const import DOMAIN, SIGNAL_NEW_POOL
from .coordinator import VistapoolDataUpdateCoordinator
from .entity import VistapoolEntity

PARALLEL_UPDATES = 1

_HASLED_PATH = "main.hasLED"
_LIGHT_STATUS_PATH = "light.status"
_LED_PULSE_DELAY_SECONDS = 1.0


def _build_button_entities(
    coordinator: VistapoolDataUpdateCoordinator,
) -> list[VistapoolLEDPulseButton]:
    """Build the button entities for a single pool."""
    if not coordinator.get_value(_HASLED_PATH):
        return []
    return [VistapoolLEDPulseButton(coordinator)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VistapoolConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Vistapool buttons for every pool that has an LED fixture."""
    entities: list[VistapoolLEDPulseButton] = []
    for coordinator in entry.runtime_data.coordinators.values():
        entities.extend(_build_button_entities(coordinator))
    async_add_entities(entities)

    @callback
    def _async_add_pool(coordinator: VistapoolDataUpdateCoordinator) -> None:
        async_add_entities(_build_button_entities(coordinator))

    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{SIGNAL_NEW_POOL}_{entry.entry_id}", _async_add_pool
        )
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

    @override
    async def async_press(self) -> None:
        """Send a color-advance pulse to the pool LED fixture."""
        # Serialized with the light entity, which writes the same path: an
        # interleaved write would break the pending-order/wire-order match.
        async with self.coordinator.write_lock(_LIGHT_STATUS_PATH):
            await self._async_pulse()

    async def _async_pulse(self) -> None:
        """Run the pulse sequence; caller holds the light.status write lock."""
        if self.coordinator.get_value(_LIGHT_STATUS_PATH) not in (True, "1"):
            await self._async_write_status(1)
            self.coordinator.apply_optimistic(_LIGHT_STATUS_PATH, 1)
            return
        # Queue the whole off/on sequence before the first send: the echoes
        # are then confirmed in order, and a push landing inside the pulse
        # delay is overlaid with the final on instead of the transient off,
        # so the light entity never flickers. A failed send discards the
        # writes the cloud never acknowledged.
        self.coordinator.record_optimistic(_LIGHT_STATUS_PATH, 0)
        self.coordinator.record_optimistic(_LIGHT_STATUS_PATH, 1)
        try:
            await self._async_write_status(0)
        except HomeAssistantError:
            self.coordinator.discard_optimistic(_LIGHT_STATUS_PATH)
            self.coordinator.discard_optimistic(_LIGHT_STATUS_PATH)
            # A push consumed mid-send may have been overlaid with a queued
            # value that just got discarded; fetch the truth.
            self.coordinator.start_self_heal()
            raise
        await asyncio.sleep(_LED_PULSE_DELAY_SECONDS)
        try:
            await self._async_write_status(1)
        except HomeAssistantError:
            self.coordinator.discard_optimistic(_LIGHT_STATUS_PATH)
            self.coordinator.start_self_heal()
            raise
        # The on write was queued before the off send and the pulse delay;
        # restart its TTL now so it covers the round trip of its own send.
        self.coordinator.refresh_optimistic(_LIGHT_STATUS_PATH)
        self.coordinator.async_set_updated_data(self.coordinator.data)

    async def _async_write_status(self, value: int) -> None:
        """Write light.status via the cloud API."""
        try:
            await self.coordinator.api.set_value(
                self.coordinator.pool_id, _LIGHT_STATUS_PATH, value
            )
        except AquariteError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_failed",
                translation_placeholders={"entity": self.entity_id},
            ) from err
