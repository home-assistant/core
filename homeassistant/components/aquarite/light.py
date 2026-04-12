"""Aquarite Light entity with State Reconciliation and Failure Handling."""
from __future__ import annotations

import time
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AquariteConfigEntry
from .coordinator import AquariteDataUpdateCoordinator
from .entity import AquariteEntity

# How long to wait for the cloud to confirm before reverting the UI
RECONCILIATION_TIMEOUT = 20

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AquariteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aquarite light platform."""
    dataservice = entry.runtime_data.coordinator
    pool_id, pool_name = dataservice.pool_id, entry.title

    async_add_entities([
        AquariteLightEntity(dataservice, pool_id, pool_name, "pool_light", "light.status")
    ])


class AquariteLightEntity(AquariteEntity, LightEntity):
    """Representation of an Aquarite pool light."""

    _attr_supported_color_modes = {ColorMode.ONOFF}
    _attr_color_mode = ColorMode.ONOFF

    def __init__(
        self,
        dataservice: AquariteDataUpdateCoordinator,
        pool_id: str,
        pool_name: str,
        translation_key: str,
        value_path: str,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(dataservice, pool_id, pool_name)
        self._value_path = value_path
        self._attr_translation_key = translation_key
        self._attr_unique_id = self.build_unique_id(translation_key)

        # Reconciliation logic
        self._target_state: bool | None = None
        self._target_set_at: float = 0

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        actual_state = bool(self.coordinator.get_value(self._value_path))

        # If we aren't waiting for a change, show actual state
        if self._target_state is None:
            return actual_state

        # Check if the cloud has finally matched our request
        if actual_state == self._target_state:
            self._target_state = None
            return actual_state

        # Check if we've waited too long (Timeout)
        if (time.monotonic() - self._target_set_at) > RECONCILIATION_TIMEOUT:
            self._target_state = None
            return actual_state

        # Otherwise, stay optimistic
        return self._target_state

    async def _send_command(self, state: bool) -> None:
        """Set target state and trigger API."""
        self._target_state = state
        self._target_set_at = time.monotonic()
        self.async_write_ha_state()

        try:
            await self.coordinator.api.set_value(
                self._pool_id, self._value_path, 1 if state else 0
            )
        except Exception:
            # If the API call fails immediately, reset and revert UI
            self._target_state = None
            self.async_write_ha_state()
            raise

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._send_command(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._send_command(False)
