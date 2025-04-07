"""Support for Bosch Alarm Panel outputs and doors as switches."""

from __future__ import annotations

from typing import Any

from bosch_alarm_mode2 import Panel

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN


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
        PanelDoorSecuredEntity(
            panel,
            door_id,
            config_entry.unique_id or config_entry.entry_id,
        )
        for door_id in panel.doors
    )

    entities.extend(
        PanelDoorCyclingEntity(
            panel,
            door_id,
            config_entry.unique_id or config_entry.entry_id,
        )
        for door_id in panel.doors
    )

    async_add_entities(entities)


PARALLEL_UPDATES = 0


class PanelDoorEntity(SwitchEntity):
    """A switch entity for a door on a bosch alarm panel."""

    _attr_has_entity_name = True

    def __init__(self, panel: Panel, door_id: int, unique_id: str, type: str) -> None:
        """Set up a switch entity for a door on a bosch alarm panel."""
        self.panel = panel
        self._door = panel.doors[door_id]
        door_unique_id = f"{unique_id}_door_{door_id}"
        self._attr_unique_id = f"{door_unique_id}_{type}"
        self._attr_translation_key = type
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, door_unique_id)},
            name=self._door.name,
            manufacturer="Bosch Security Systems",
            via_device=(
                DOMAIN,
                unique_id,
            ),
        )
        self._door_id = door_id

    @property
    def available(self) -> bool:
        """Return if the door is available."""
        return (
            self._door.is_open()
            or self._door.is_locked()
            or self._door.is_secured()
            or self._door.is_cycling()
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._door.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._door.status_observer.detach(self.schedule_update_ha_state)


class PanelDoorLockedEntity(PanelDoorEntity):
    """A switch entity for a door on a bosch alarm panel."""

    def __init__(self, panel: Panel, door_id: int, unique_id: str) -> None:
        """Set up a switch entity for a door on a bosch alarm panel."""
        super().__init__(panel, door_id, unique_id, "locked")
        self._attr_name = "Locked"

    @property
    def is_on(self) -> bool:
        """Return if the door is locked."""
        return self._door.is_locked()

    @property
    def available(self) -> bool:
        """Return if the door is available."""
        return self._door.is_open() or self._door.is_locked()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self.panel.door_relock(self._door_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self.panel.door_unlock(self._door_id)


class PanelDoorSecuredEntity(PanelDoorEntity):
    """A switch entity for a doors secured state on a bosch alarm panel."""

    def __init__(self, panel: Panel, door_id: int, unique_id: str) -> None:
        """Set up a switch entity for a door on a bosch alarm panel."""
        super().__init__(panel, door_id, unique_id, "secured")
        self._attr_name = "Secured"

    @property
    def is_on(self) -> bool:
        """Return if the door is secured."""
        return self._door.is_secured()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self.panel.door_secure(self._door_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self.panel.door_unsecure(self._door_id)


class PanelDoorCyclingEntity(PanelDoorEntity):
    """A switch entity for a doors cycling state on a bosch alarm panel."""

    def __init__(self, panel: Panel, door_id: int, unique_id: str) -> None:
        """Set up a switch entity for a door on a bosch alarm panel."""
        super().__init__(panel, door_id, unique_id, "cycling")
        self._attr_name = "Cycling"

    @property
    def is_on(self) -> bool:
        """Return if the door is cycling."""
        return self._door.is_cycling()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock the door."""
        await self.panel.door_cycle(self._door_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock the door."""
        await self.panel.door_relock(self._door_id)


class PanelOutputEntity(SwitchEntity):
    """An output entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, panel: Panel, output_id: int, unique_id: str) -> None:
        """Set up an output entity for a bosch alarm panel."""
        self.panel = panel
        self._output = panel.outputs[output_id]
        self._output_id = output_id
        self._observer = self._output.status_observer
        self._attr_unique_id = f"{unique_id}_output_{output_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._output.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
            via_device=(
                DOMAIN,
                unique_id,
            ),
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._observer.detach(self.schedule_update_ha_state)

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
