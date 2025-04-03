"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschAlarmConfigEntry
from .const import DOMAIN

READY_STATE_NO = "no"
READY_STATE_HOME = "home"
READY_STATE_AWAY = "away"


async def async_setup_entry(
    hass: HomeAssistant | None,
    config_entry: BoschAlarmConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a sensor for tracking panel history."""

    panel = config_entry.runtime_data
    unique_id = config_entry.unique_id or config_entry.entry_id
    async_add_entities(
        [
            PanelHistorySensor(panel, unique_id),
            PanelFaultsSensor(panel, unique_id),
        ]
    )
    async_add_entities(
        AreaReadyToArmSensor(
            panel,
            area_id,
            f"{unique_id}_area_{area_id}",
        )
        for area_id in panel.areas
    )
    async_add_entities(
        FaultingPointsSensor(
            panel,
            area_id,
            f"{unique_id}_area_{area_id}",
        )
        for area_id in panel.areas
    )
    async_add_entities(
        AreaAlarmsSensor(
            panel,
            area_id,
            f"{unique_id}_area_{area_id}",
        )
        for area_id in panel.areas
    )


PARALLEL_UPDATES = 0


class PanelHistorySensor(SensorEntity):
    """A history sensor entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = "History"

    def __init__(self, panel: Panel, unique_id: str) -> None:
        """Set up a history sensor entity for a bosch alarm panel."""
        self.panel = panel
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{unique_id}_history"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=f"Bosch {panel.model}",
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def icon(self) -> str | None:
        """The icon for this history entity."""
        return "mdi:history"

    @property
    def native_value(self) -> str:
        """The state for this history entity."""
        events = self.panel.events
        if events:
            return str(events[-1])
        return "No events"

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self.panel.history_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self.panel.history_observer.detach(self.schedule_update_ha_state)


class PanelFaultsSensor(SensorEntity):
    """A faults sensor entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_name = "Faults"
    _attr_translation_key = "panel_faults"

    def __init__(self, panel: Panel, unique_id: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        self.panel = panel
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = f"{unique_id}_faults"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=f"Bosch {panel.model}",
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def native_value(self) -> str:
        """The state of this faults entity."""
        faults = self.panel.panel_faults
        return "\n".join(faults) if faults else "No faults"

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        self.panel.faults_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self.panel.faults_observer.detach(self.schedule_update_ha_state)


class FaultingPointsSensor(SensorEntity):
    """A faults sensor entity for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "faulting_points"

    def __init__(self, panel: Panel, area_id: int, unique_id: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        self.panel = panel
        self._area = panel.areas[area_id]
        self._attr_unique_id = f"{unique_id}_faults"
        self._attr_name = f"{self._area.name} Faulting Points"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def native_value(self) -> str:
        """The state of this faults entity."""
        return f"{self._area.faults}"

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self.panel.faults_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self.panel.faults_observer.detach(self.schedule_update_ha_state)


class AreaReadyToArmSensor(SensorEntity):
    """A sensor entity showing the ready state for an area for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "ready_to_arm"

    def __init__(self, panel: Panel, area_id: int, unique_id: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        self.panel = panel
        self._area = panel.areas[area_id]
        self._attr_unique_id = f"{unique_id}_ready_to_arm"
        self._attr_should_poll = False
        self._attr_name = f"{self._area.name} Ready To Arm"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def native_value(self) -> str:
        """The state of this entity."""
        if self._area.all_ready:
            return READY_STATE_AWAY
        if self._area.part_ready:
            return READY_STATE_HOME
        return READY_STATE_NO

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._area.ready_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._area.ready_observer.attach(self.schedule_update_ha_state)


class AreaAlarmsSensor(SensorEntity):
    """A sensor entity showing the alarms for an area for a bosch alarm panel."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, panel: Panel, area_id: int, unique_id: str) -> None:
        """Set up a faults sensor entity for a bosch alarm panel."""
        self.panel = panel
        self._area = panel.areas[area_id]
        self._attr_unique_id = f"{unique_id}_alarms"
        self._attr_should_poll = False
        self._attr_name = f"{self._area.name} Alarms"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            model=panel.model,
            sw_version=panel.firmware_version,
        )

    @property
    def icon(self) -> str:
        """The icon for this alarms entity."""
        return "mdi:alert-circle-outline"

    @property
    def native_value(self) -> str:
        """The state of this alarms entity."""
        return "\n".join(self._area.alarms) if self._area.alarms else "No Alarms"

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._area.alarm_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self._area.alarm_observer.attach(self.schedule_update_ha_state)
