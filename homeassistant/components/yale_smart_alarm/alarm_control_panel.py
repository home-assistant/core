"""Support for Yale Alarm."""

from __future__ import annotations

from typing import TYPE_CHECKING

from yalesmartalarmclient.const import (
    YALE_STATE_ARM_FULL,
    YALE_STATE_ARM_PARTIAL,
    YALE_STATE_DISARM,
)

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import YaleConfigEntry
from .const import DOMAIN, STATE_MAP, YALE_ALL_ERRORS
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: YaleConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the alarm entry."""

    async_add_entities([YaleAlarmDevice(coordinator=entry.runtime_data)])


class YaleAlarmDevice(YaleAlarmEntity, AlarmControlPanelEntity):
    """Represent a Yale Smart Alarm."""

    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_name = None

    def __init__(self, coordinator: YaleDataUpdateCoordinator) -> None:
        """Initialize the Yale Alarm Device."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.entry.entry_id

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        return await self.async_set_alarm(YALE_STATE_DISARM, code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        return await self.async_set_alarm(YALE_STATE_ARM_PARTIAL, code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        return await self.async_set_alarm(YALE_STATE_ARM_FULL, code)

    async def async_set_alarm(self, command: str, code: str | None = None) -> None:
        """Set alarm."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"

        try:
            if command == YALE_STATE_ARM_FULL:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.arm_full
                )
            if command == YALE_STATE_ARM_PARTIAL:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.arm_partial
                )
            if command == YALE_STATE_DISARM:
                alarm_state = await self.hass.async_add_executor_job(
                    self.coordinator.yale.disarm
                )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_alarm",
                translation_placeholders={
                    "name": self.coordinator.entry.data[CONF_NAME],
                    "error": str(error),
                },
            ) from error

        if alarm_state:
            self.coordinator.data["alarm"] = command
            self.async_write_ha_state()
            return
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="could_not_change_alarm",
        )

    @property
    def available(self) -> bool:
        """Return True if alarm is available."""
        if STATE_MAP.get(self.coordinator.data["alarm"]) is None:
            return False
        return super().available

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm."""
        return STATE_MAP.get(self.coordinator.data["alarm"])
