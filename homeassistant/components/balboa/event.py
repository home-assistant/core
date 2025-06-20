"""Support for Balboa events."""

from __future__ import annotations

from datetime import datetime, timedelta

from pybalboa import EVENT_UPDATE, SpaClient

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import BalboaConfigEntry
from .entity import BalboaEntity

FAULT = "fault"
FAULT_DATE = "fault_date"
REQUEST_FAULT_LOG_INTERVAL = timedelta(minutes=5)

FAULT_MESSAGE_CODE_MAP: dict[int, str] = {
    15: "sensor_out_of_sync",
    16: "low_flow",
    17: "flow_failed",
    18: "settings_reset",
    19: "priming_mode",
    20: "clock_failed",
    21: "settings_reset",
    22: "memory_failure",
    26: "service_sensor_sync",
    27: "heater_dry",
    28: "heater_may_be_dry",
    29: "water_too_hot",
    30: "heater_too_hot",
    31: "sensor_a_fault",
    32: "sensor_b_fault",
    34: "pump_stuck",
    35: "hot_fault",
    36: "gfci_test_failed",
    37: "standby_mode",
}
FAULT_EVENT_TYPES = sorted(set(FAULT_MESSAGE_CODE_MAP.values()))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BalboaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the spa's events."""
    async_add_entities([BalboaEventEntity(entry.runtime_data)])


class BalboaEventEntity(BalboaEntity, EventEntity):
    """Representation of a Balboa event entity."""

    _attr_event_types = FAULT_EVENT_TYPES
    _attr_translation_key = FAULT

    def __init__(self, spa: SpaClient) -> None:
        """Initialize a Balboa event entity."""
        super().__init__(spa, FAULT)

    @callback
    def _async_handle_event(self) -> None:
        """Handle the fault event."""
        if not (fault := self._client.fault):
            return
        fault_date = fault.fault_datetime.isoformat()
        if self.state_attributes.get(FAULT_DATE) != fault_date:
            self._trigger_event(
                FAULT_MESSAGE_CODE_MAP.get(fault.message_code, fault.message),
                {FAULT_DATE: fault_date, "code": fault.message_code},
            )
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._client.on(EVENT_UPDATE, self._async_handle_event))

        async def request_fault_log(now: datetime | None = None) -> None:
            """Request the most recent fault log."""
            await self._client.request_fault_log()

        await request_fault_log()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, request_fault_log, REQUEST_FAULT_LOG_INTERVAL
            )
        )
