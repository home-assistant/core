"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel
from bosch_alarm_mode2.const import ALARM_MEMORY_PRIORITIES

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN

priority_types = {
    "burglary": {
        "alarm": ALARM_MEMORY_PRIORITIES.BURGLARY_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.BURGLARY_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.BURGLARY_TROUBLE,
    },
    "gas": {
        "alarm": ALARM_MEMORY_PRIORITIES.GAS_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.GAS_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.GAS_TROUBLE,
    },
    "fire": {
        "alarm": ALARM_MEMORY_PRIORITIES.FIRE_ALARM,
        "supervisory": ALARM_MEMORY_PRIORITIES.FIRE_SUPERVISORY,
        "trouble": ALARM_MEMORY_PRIORITIES.FIRE_TROUBLE,
    },
    "personal": {"emergency": ALARM_MEMORY_PRIORITIES.PERSONAL_EMERGENCY},
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a sensor for tracking panel history."""

    panel = config_entry.runtime_data
    unique_id = config_entry.unique_id or config_entry.entry_id
    entities: list[SensorEntity] = [
        FaultingPointsSensor(
            panel,
            area_id,
            unique_id,
        )
        for area_id in panel.areas
    ]

    entities.extend(
        AreaAlarmsSensor(panel, area_id, unique_id, "burglary")
        for area_id in panel.areas
    )

    entities.extend(
        AreaAlarmsSensor(panel, area_id, unique_id, "gas") for area_id in panel.areas
    )

    entities.extend(
        AreaAlarmsSensor(panel, area_id, unique_id, "fire") for area_id in panel.areas
    )

    entities.extend(
        AreaAlarmsSensor(panel, area_id, unique_id, "personal")
        for area_id in panel.areas
    )
    async_add_entities(entities)


PARALLEL_UPDATES = 0


class AreaSensor(SensorEntity):
    """A faults sensor entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, panel: Panel, area_id: int, unique_id: str, type: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        self.panel = panel
        area_unique_id = f"{unique_id}_area_{area_id}"
        self._attr_translation_key = type
        self._area = panel.areas[area_id]
        self._attr_unique_id = f"{area_unique_id}_{type}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, area_unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._area.alarm_observer.attach(self.schedule_update_ha_state)
        self._area.ready_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._area.alarm_observer.detach(self.schedule_update_ha_state)
        self._area.ready_observer.detach(self.schedule_update_ha_state)


class FaultingPointsSensor(AreaSensor):
    """A faults sensor entity for a bosch alarm panel."""

    def __init__(self, panel: Panel, area_id: int, unique_id: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        super().__init__(panel, area_id, unique_id, "faulting_points")

    @property
    def native_value(self) -> str:
        """The state of this faults entity."""
        return str(self._area.faults)


class AreaAlarmsSensor(AreaSensor):
    """A sensor entity showing the alarms for an area for a bosch alarm panel."""

    def __init__(self, panel: Panel, area_id: int, unique_id: str, type: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        super().__init__(panel, area_id, unique_id, f"alarms_{type}")
        self.type = type

    @property
    def native_value(self) -> str:
        """The state of this alarms entity."""
        for state, priority in priority_types[self.type].items():
            if priority in self._area.alarms_ids:
                return state
        return "no_alarms"
