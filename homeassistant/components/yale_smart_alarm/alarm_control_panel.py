"""Support for Yale Alarm."""
from __future__ import annotations

import asyncio

from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the alarm platform."""
    return True


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the alarm entry."""

    async_add_entities(
        [YaleAlarmDevice(coordinator=hass.data[DOMAIN][entry.entry_id]["coordinator"])]
    )


class YaleAlarmDevice(CoordinatorEntity, AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    coordinator: YaleDataUpdateCoordinator

    _state_map = {
        YALE_STATE_DISARM: STATE_ALARM_DISARMED,
        YALE_STATE_ARM_PARTIAL: STATE_ALARM_ARMED_HOME,
        YALE_STATE_ARM_FULL: STATE_ALARM_ARMED_AWAY,
    }

    _state = STATE_UNAVAILABLE

    @property
    def name(self):
        """Return the name of the device."""
        return "Yale Smart Alarm"

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    async def _async_set_arm_state(self, state) -> None:
        """Send set arm state command."""
        if state == "arm":
            await self.hass.async_add_executor_job(self.coordinator._yale.arm_full())  # type: ignore[attr-defined]
        elif state == "home":
            await self.hass.async_add_executor_job(self.coordinator._yale.arm_partial())  # type: ignore[attr-defined]
        elif state == "disarm":
            await self.hass.async_add_executor_job(self.coordinator._yale.disarm())  # type: ignore[attr-defined]

        LOGGER.debug("Yale set arm state %s", state)
        transaction = None
        while state != transaction:
            await asyncio.sleep(0.5)
            transaction = await self.hass.async_add_executor_job(
                self.coordinator._yale.get_armed_status()  # type: ignore[attr-defined]
            )

        await self.coordinator.async_refresh()

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._async_set_arm_state("disarm")

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._async_set_arm_state("home")

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._async_set_arm_state("arm")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._state = self._state_map.get(
            self.coordinator.data["alarm"], STATE_UNAVAILABLE
        )
        super()._handle_coordinator_update()

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()
