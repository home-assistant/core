"""Alarm control panel for LocknAlert partitions."""

from __future__ import annotations

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.const import STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .__init__ import LocknAlertConfigEntry
from .const import CONF_BRIDGE_SERIAL
from .entity import LocknAlertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: LocknAlertConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data.coordinator
    bridge_serial = str(entry.data[CONF_BRIDGE_SERIAL])
    entities = [
        LocknAlertPartitionAlarm(bridge_serial, partition_id, partition, coordinator.state.available)
        for partition_id, partition in coordinator.state.partitions.items()
    ]
    if entities:
        async_add_entities(entities)


class LocknAlertPartitionAlarm(LocknAlertEntity, AlarmControlPanelEntity):
    def __init__(self, bridge_id: str, partition_id: str, partition: dict, available: bool) -> None:
        super().__init__(bridge_id, f"partition_{partition_id}")
        self._partition = partition
        self._available = available
        self._attr_name = partition.get("name", f"Partition {partition_id}")

    @property
    def alarm_state(self) -> str | None:
        state = str(self._partition.get("state", "disarmed")).lower()
        if state in {"away", "armed_away"}:
            return STATE_ALARM_ARMED_AWAY
        if state in {"home", "armed_home", "stay"}:
            return STATE_ALARM_ARMED_HOME
        return STATE_ALARM_DISARMED
