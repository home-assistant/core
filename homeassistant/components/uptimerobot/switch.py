"""UptimeRobot switch platform."""

from typing import Any

from pyuptimerobot import UptimeRobotMonitor

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUSES_ON
from .coordinator import UptimeRobotConfigEntry
from .entity import UptimeRobotEntity
from .utils import new_device_listener, uptimerobot_api_call

# Limit the number of parallel updates to 1
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UptimeRobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UptimeRobot switches."""
    coordinator = entry.runtime_data

    def _add_new_entities(new_monitors: list[UptimeRobotMonitor]) -> None:
        """Add entities for new monitors."""
        entities = [
            UptimeRobotSwitch(
                coordinator,
                SwitchEntityDescription(
                    key=str(monitor.id),
                    device_class=SwitchDeviceClass.SWITCH,
                ),
            )
            for monitor in new_monitors
        ]
        if entities:
            async_add_entities(entities)

    entry.async_on_unload(new_device_listener(coordinator, _add_new_entities))


class UptimeRobotSwitch(UptimeRobotEntity, SwitchEntity):
    """Representation of a UptimeRobot switch."""

    _attr_translation_key = "monitor_status"

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return bool(self._monitor.status in STATUSES_ON)

    @uptimerobot_api_call
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.api.async_pause_monitor(monitor_id=self._monitor.id)
        await self.coordinator.async_request_refresh()

    @uptimerobot_api_call
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.api.async_start_monitor(monitor_id=self._monitor.id)
        await self.coordinator.async_request_refresh()
