"""Support for IDS Hyyp alarms."""
from __future__ import annotations

from typing import Any

from pyhyypapi.exceptions import HTTPError, HyypApiError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_ARM_CODE, DATA_COORDINATOR, DOMAIN
from .coordinator import HyypDataUpdateCoordinator
from .entity import HyypPartitionEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Ezviz alarm control panel."""
    coordinator: HyypDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    arm_code = entry.options.get(ATTR_ARM_CODE)

    async_add_entities(
        [
            HyypAlarm(coordinator, site_id, partition_id, arm_code)
            for site_id in coordinator.data
            for partition_id in coordinator.data[site_id]["partitions"]
        ]
    )


class HyypAlarm(HyypPartitionEntity, AlarmControlPanelEntity):
    """Representation of a Hyyp alarm control panel."""

    coordinator: HyypDataUpdateCoordinator
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.TRIGGER
    )
    _attr_code_format = CodeFormat.NUMBER

    def __init__(
        self,
        coordinator: HyypDataUpdateCoordinator,
        site_id: int,
        partition_id: int,
        arm_code: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, site_id, partition_id)
        self._attr_name = self.partition_data["name"]
        self._arm_code = arm_code
        self._attr_unique_id = f"{self._site_id}_{partition_id}"
        self._attr_code_arm_required = bool(arm_code)
        self._arm_home_profile_id = list(self.partition_data["stayProfiles"])[
            0
        ]  # Supports multiple stay profiles. Assume first is arm home.

    @property
    def available(self) -> bool:
        """Check if device is reporting online from api."""
        return bool(self.data["isOnline"])

    @property
    def state(self) -> StateType:
        """Update alarm state."""

        if self.partition_data["alarm"]:
            return STATE_ALARM_TRIGGERED

        if self.partition_data["armed"]:
            if self.partition_data["stayArmed"]:
                return STATE_ALARM_ARMED_HOME

            return STATE_ALARM_ARMED_AWAY

        return STATE_ALARM_DISARMED

    async def async_alarm_disarm(self, code: Any = None) -> None:
        """Send disarm command."""
        _code = code if not bool(self._arm_code) else self._arm_code

        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.hyyp_client.arm_site,
                self._site_id,
                False,
                _code,
                self._partition_id,
            )

        except (HTTPError, HyypApiError) as err:
            raise HyypApiError("Cannot disarm alarm") from err

        if update_ok["status"] == "SUCCESS":
            await self.coordinator.async_request_refresh()

        else:
            raise HTTPError(f"Cannot disarm alarm: {update_ok}")

    async def async_alarm_arm_away(self, code: Any = None) -> None:
        """Send arm away command."""
        _code = code if not bool(self._arm_code) else self._arm_code

        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.hyyp_client.arm_site,
                self._site_id,
                True,
                _code,
                self._partition_id,
            )

        except (HTTPError, HyypApiError) as err:
            raise HyypApiError("Cannot arm alarm") from err

        if update_ok["status"] == "SUCCESS":
            await self.coordinator.async_request_refresh()

        else:
            raise HTTPError(f"Cannot arm alarm, check for violated zones. {update_ok}")

    async def async_alarm_arm_home(self, code: Any = None) -> None:
        """Send arm home command."""
        _code = code if not bool(self._arm_code) else self._arm_code

        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.hyyp_client.arm_site,
                self._site_id,
                True,
                _code,
                self._partition_id,
                self._arm_home_profile_id,
            )

        except (HTTPError, HyypApiError) as err:
            raise HyypApiError("Cannot arm home alarm") from err

        if update_ok["status"] == "SUCCESS":
            await self.coordinator.async_request_refresh()

        else:
            raise HTTPError(
                f"Cannot arm home alarm, check for violated zones. {update_ok}"
            )

    async def async_alarm_trigger(self, code: Any = None) -> None:
        """Send alarm trigger."""
        _code = code if not bool(self._arm_code) else self._arm_code

        try:
            update_ok = await self.hass.async_add_executor_job(
                self.coordinator.hyyp_client.trigger_alarm,
                self._site_id,
                _code,
                self._partition_id,
            )

        except (HTTPError, HyypApiError) as err:
            raise HyypApiError("Cannot trigger alarm") from err

        if update_ok["status"] == "SUCCESS":
            await self.coordinator.async_request_refresh()

        else:
            raise HTTPError(f"Cannot trigger alarm. {update_ok}")
