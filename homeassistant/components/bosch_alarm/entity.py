"""Support for Bosch Alarm Panel History as a sensor."""

from __future__ import annotations

from bosch_alarm_mode2 import Panel

from homeassistant.components.sensor import Entity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN

PARALLEL_UPDATES = 0


class BoschAlarmEntity(Entity):
    """A base entity for a bosch alarm panel."""

    _attr_has_entity_name = True

    def __init__(self, panel: Panel, unique_id: str) -> None:
        """Set up a entity for a bosch alarm panel."""
        self.panel = panel
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=f"Bosch {panel.model}",
            manufacturer="Bosch Security Systems",
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.panel.connection_status()

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        self.panel.connection_status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        self.panel.connection_status_observer.detach(self.schedule_update_ha_state)


class BoschAlarmAreaEntity(BoschAlarmEntity):
    """A base entity for area related entities within a bosch alarm panel."""

    def __init__(
        self,
        panel: Panel,
        area_id: int,
        unique_id: str,
        observe_alarms: bool,
        observe_ready: bool,
        observe_status: bool,
    ) -> None:
        """Set up a area related entity for a bosch alarm panel."""
        super().__init__(panel, unique_id)
        self._area_id = area_id
        self._area_unique_id = f"{unique_id}_area_{area_id}"
        self._observe_alarms = observe_alarms
        self._observe_ready = observe_ready
        self._observe_status = observe_status
        self._area = panel.areas[area_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._area_unique_id)},
            name=self._area.name,
            manufacturer="Bosch Security Systems",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        if self._observe_alarms:
            self._area.alarm_observer.attach(self.schedule_update_ha_state)
        if self._observe_ready:
            self._area.ready_observer.attach(self.schedule_update_ha_state)
        if self._observe_status:
            self._area.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        await super().async_added_to_hass()
        if self._observe_alarms:
            self._area.alarm_observer.detach(self.schedule_update_ha_state)
        if self._observe_ready:
            self._area.ready_observer.detach(self.schedule_update_ha_state)
        if self._observe_status:
            self._area.status_observer.detach(self.schedule_update_ha_state)


class BoschAlarmDoorEntity(BoschAlarmEntity):
    """A base entity for area related entities within a bosch alarm panel."""

    def __init__(self, panel: Panel, door_id: int, unique_id: str) -> None:
        """Set up a area related entity for a bosch alarm panel."""
        super().__init__(panel, unique_id)
        self._door_id = door_id
        self._door = panel.doors[door_id]
        self._door_unique_id = f"{unique_id}_door_{door_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._door_unique_id)},
            name=self._door.name,
            manufacturer="Bosch Security Systems",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._door.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        await super().async_added_to_hass()
        self._door.status_observer.detach(self.schedule_update_ha_state)


class BoschAlarmOutputEntity(BoschAlarmEntity):
    """A base entity for area related entities within a bosch alarm panel."""

    def __init__(self, panel: Panel, output_id: int, unique_id: str) -> None:
        """Set up a output related entity for a bosch alarm panel."""
        super().__init__(panel, unique_id)
        self._output_id = output_id
        self._output = panel.outputs[output_id]
        self._output_unique_id = f"{unique_id}_output_{output_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._output_unique_id)},
            name=self._output.name,
            manufacturer="Bosch Security Systems",
            via_device=(DOMAIN, unique_id),
        )

    async def async_added_to_hass(self) -> None:
        """Observe state changes."""
        await super().async_added_to_hass()
        self._output.status_observer.attach(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Stop observing state changes."""
        await super().async_added_to_hass()
        self._output.status_observer.detach(self.schedule_update_ha_state)
