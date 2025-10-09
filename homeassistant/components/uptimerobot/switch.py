"""UptimeRobot switch platform."""

from __future__ import annotations

from typing import Any

from pyuptimerobot import (
    UptimeRobotAuthenticationException,
    UptimeRobotException,
    UptimeRobotMonitor,
)

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import API_ATTR_OK, DOMAIN
from .coordinator import UptimeRobotConfigEntry
from .entity import UptimeRobotEntity
from .utils import new_device_listener

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
                monitor=monitor,
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
        return bool(self.monitor.status != 0)

    async def _async_edit_monitor(self, **kwargs: Any) -> None:
        """Edit monitor status."""
        try:
            response = await self.api.async_edit_monitor(**kwargs)
        except UptimeRobotAuthenticationException:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            return
        except UptimeRobotException as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_exception",
                translation_placeholders={"error": repr(exception)},
            ) from exception

        if response.status != API_ATTR_OK:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="api_exception",
                translation_placeholders={"error": response.error.message},
            )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_edit_monitor(id=self.monitor.id, status=0)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_edit_monitor(id=self.monitor.id, status=1)
