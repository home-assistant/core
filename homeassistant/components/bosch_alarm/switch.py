"""Support for Bosch Alarm Panel outputs and doors as switches."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.panel import Door

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN
from .entity import BoschAlarmDoorEntity, BoschAlarmOutputEntity


@dataclass(kw_only=True, frozen=True)
class BoschAlarmSwitchEntityDescription(SwitchEntityDescription):
    """Describes Bosch Alarm door entity."""

    value_fn: Callable[[Door], bool]
    on_fn: Callable[[Panel, int], Coroutine[Any, Any, None]]
    off_fn: Callable[[Panel, int], Coroutine[Any, Any, None]]


DOOR_SWITCH_TYPES: list[BoschAlarmSwitchEntityDescription] = [
    BoschAlarmSwitchEntityDescription(
        key="locked",
        translation_key="locked",
        value_fn=lambda door: door.is_locked(),
        on_fn=lambda panel, door_id: panel.door_relock(door_id),
        off_fn=lambda panel, door_id: panel.door_unlock(door_id),
    ),
    BoschAlarmSwitchEntityDescription(
        key="secured",
        translation_key="secured",
        value_fn=lambda door: door.is_secured(),
        on_fn=lambda panel, door_id: panel.door_secure(door_id),
        off_fn=lambda panel, door_id: panel.door_unsecure(door_id),
    ),
    BoschAlarmSwitchEntityDescription(
        key="cycling",
        translation_key="cycling",
        value_fn=lambda door: door.is_cycling(),
        on_fn=lambda panel, door_id: panel.door_cycle(door_id),
        off_fn=lambda panel, door_id: panel.door_relock(door_id),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities for outputs."""

    panel = config_entry.runtime_data
    entities: list[SwitchEntity] = [
        PanelOutputEntity(
            panel, output_id, config_entry.unique_id or config_entry.entry_id
        )
        for output_id in panel.outputs
    ]

    entities.extend(
        PanelDoorEntity(
            panel,
            door_id,
            config_entry.unique_id or config_entry.entry_id,
            entity_description,
        )
        for door_id in panel.doors
        for entity_description in DOOR_SWITCH_TYPES
    )

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class PanelDoorEntity(BoschAlarmDoorEntity, SwitchEntity):
    """A switch entity for a door on a bosch alarm panel."""

    entity_description: BoschAlarmSwitchEntityDescription

    def __init__(
        self,
        panel: Panel,
        door_id: int,
        unique_id: str,
        entity_description: BoschAlarmSwitchEntityDescription,
    ) -> None:
        """Set up a switch entity for a door on a bosch alarm panel."""
        super().__init__(panel, door_id, unique_id)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self._door_unique_id}_{entity_description.key}"

    @property
    def is_on(self) -> bool:
        """Return the value function."""
        return self.entity_description.value_fn(self._door)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Run the on function."""
        # If the door is currently cycling, we can't send it any other commands until it is done
        if self._door.is_cycling():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="incorrect_door_state"
            )
        await self.entity_description.on_fn(self.panel, self._door_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Run the off function."""
        # If the door is currently cycling, we can't send it any other commands until it is done
        if self._door.is_cycling():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="incorrect_door_state"
            )
        await self.entity_description.off_fn(self.panel, self._door_id)


class PanelOutputEntity(BoschAlarmOutputEntity, SwitchEntity):
    """An output entity for a bosch alarm panel."""

    _attr_name = None

    def __init__(self, panel: Panel, output_id: int, unique_id: str) -> None:
        """Set up an output entity for a bosch alarm panel."""
        super().__init__(panel, output_id, unique_id)
        self._attr_unique_id = self._output_unique_id

    @property
    def is_on(self) -> bool:
        """Check if this entity is on."""
        return self._output.is_active()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on this output."""
        await self.panel.set_output_active(self._output_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off this output."""
        await self.panel.set_output_inactive(self._output_id)
