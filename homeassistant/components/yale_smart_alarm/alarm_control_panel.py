"""Support for Yale Alarm."""
from __future__ import annotations

from yalesmartalarmclient.client import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.components.alarm_control_panel import (
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    ATTR_CODE_FORMAT,
    AlarmControlPanelEntity,
)
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_USERNAME,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import YaleDataUpdateCoordinator


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
        return self.coordinator.entry.data[CONF_NAME]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return str(self.coordinator.entry.unique_id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return {
            "name": self.coordinator.entry.data[CONF_NAME],
            "manufacturer": "Yale",
            "model": "main",
            "identifiers": {(DOMAIN, self.coordinator.entry.data[CONF_USERNAME])},
        }

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY

    async def _async_set_arm_state(self, state) -> None:
        """Send set arm state command."""
        if state == "arm":
            await self.hass.async_add_executor_job(self.coordinator.yale.arm_full)  # type: ignore[attr-defined]
            self._state = STATE_ALARM_ARMED_AWAY
        elif state == "home":
            await self.hass.async_add_executor_job(self.coordinator.yale.arm_partial)  # type: ignore[attr-defined]
            self._state = STATE_ALARM_ARMED_HOME
        elif state == "disarm":
            await self.hass.async_add_executor_job(self.coordinator.yale.disarm)  # type: ignore[attr-defined]
            self._state = STATE_ALARM_DISARMED

        LOGGER.debug("Yale set arm state %s", state)

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

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_CODE_FORMAT: self.code_format,
            ATTR_CHANGED_BY: self.changed_by,
            ATTR_CODE_ARM_REQUIRED: self.code_arm_required,
            "online": self.coordinator.data["online"],
            "status": self.coordinator.data["status"],
        }

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
