"""Switch platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .const import REG_SESSION_ACTIVE
from .entity import LeilSaunaEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LeilSaunaSwitchEntityDescription(SwitchEntityDescription):
    """Describes Saunum Leil Sauna switch entity."""

    register: int
    value_fn: Callable[[dict[str, Any]], bool]


SWITCHES: tuple[LeilSaunaSwitchEntityDescription, ...] = (
    LeilSaunaSwitchEntityDescription(
        key="session_active",
        translation_key="session_active",
        register=REG_SESSION_ACTIVE,
        value_fn=lambda data: bool(data.get("session_active")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna switch entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaSwitch(coordinator, description) for description in SWITCHES
    )


class LeilSaunaSwitch(LeilSaunaEntity, SwitchEntity):
    """Representation of a Saunum Leil Sauna switch."""

    entity_description: LeilSaunaSwitchEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        # Use optimistic state if available, otherwise use coordinator data
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Check if door is open and log warning
        door_status = self.coordinator.data.get("door_status")
        if door_status == 1:  # 1 = door open
            _LOGGER.warning("Cannot activate session while door is open")
            return

        # Set optimistic state immediately for responsive UI
        self._optimistic_state = True
        self.async_write_ha_state()

        # Write to device
        success = await self.coordinator.async_write_register(
            self.entity_description.register, 1
        )

        # Clear optimistic state after coordinator refresh
        self._optimistic_state = None
        if not success:
            # If write failed, trigger state update to revert to actual state
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        success = await self.coordinator.async_write_register(
            self.entity_description.register, 0
        )

        if not success:
            _LOGGER.warning("Failed to turn off session")
