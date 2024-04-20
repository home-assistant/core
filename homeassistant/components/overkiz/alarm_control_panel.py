"""Support for Overkiz alarm control panel."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pyoverkiz.enums import OverkizCommand, OverkizCommandParam, OverkizState
from pyoverkiz.enums.ui import UIWidget
from pyoverkiz.types import StateType as OverkizStateType

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity


@dataclass(frozen=True, kw_only=True)
class OverkizAlarmDescription(AlarmControlPanelEntityDescription):
    """Class to describe an Overkiz alarm control panel."""

    supported_features: AlarmControlPanelEntityFeature
    fn_state: Callable[[Callable[[str], OverkizStateType]], str]

    alarm_disarm: str | None = None
    alarm_disarm_args: OverkizStateType | list[OverkizStateType] = None
    alarm_arm_home: str | None = None
    alarm_arm_home_args: OverkizStateType | list[OverkizStateType] = None
    alarm_arm_night: str | None = None
    alarm_arm_night_args: OverkizStateType | list[OverkizStateType] = None
    alarm_arm_away: str | None = None
    alarm_arm_away_args: OverkizStateType | list[OverkizStateType] = None
    alarm_trigger: str | None = None
    alarm_trigger_args: OverkizStateType | list[OverkizStateType] = None


MAP_INTERNAL_STATUS_STATE: dict[str, str] = {
    OverkizCommandParam.OFF: STATE_ALARM_DISARMED,
    OverkizCommandParam.ZONE_1: STATE_ALARM_ARMED_HOME,
    OverkizCommandParam.ZONE_2: STATE_ALARM_ARMED_NIGHT,
    OverkizCommandParam.TOTAL: STATE_ALARM_ARMED_AWAY,
}


def _state_tsk_alarm_controller(select_state: Callable[[str], OverkizStateType]) -> str:
    """Return the state of the device."""
    if (
        cast(str, select_state(OverkizState.INTERNAL_INTRUSION_DETECTED))
        == OverkizCommandParam.DETECTED
    ):
        return STATE_ALARM_TRIGGERED

    if cast(str, select_state(OverkizState.INTERNAL_CURRENT_ALARM_MODE)) != cast(
        str, select_state(OverkizState.INTERNAL_TARGET_ALARM_MODE)
    ):
        return STATE_ALARM_PENDING

    return MAP_INTERNAL_STATUS_STATE[
        cast(str, select_state(OverkizState.INTERNAL_TARGET_ALARM_MODE))
    ]


MAP_CORE_ACTIVE_ZONES: dict[str, str] = {
    OverkizCommandParam.A: STATE_ALARM_ARMED_HOME,
    f"{OverkizCommandParam.A},{OverkizCommandParam.B}": STATE_ALARM_ARMED_NIGHT,
    f"{OverkizCommandParam.A},{OverkizCommandParam.B},{OverkizCommandParam.C}": STATE_ALARM_ARMED_AWAY,
}


def _state_stateful_alarm_controller(
    select_state: Callable[[str], OverkizStateType],
) -> str:
    """Return the state of the device."""
    if state := cast(str, select_state(OverkizState.CORE_ACTIVE_ZONES)):
        # The Stateful Alarm Controller has 3 zones with the following options:
        # (A, B, C, A,B, B,C, A,C, A,B,C). Since it is not possible to map this to AlarmControlPanel entity,
        # only the most important zones are mapped, other zones can only be disarmed.
        if state in MAP_CORE_ACTIVE_ZONES:
            return MAP_CORE_ACTIVE_ZONES[state]

        return STATE_ALARM_ARMED_CUSTOM_BYPASS

    return STATE_ALARM_DISARMED


MAP_MYFOX_STATUS_STATE: dict[str, str] = {
    OverkizCommandParam.ARMED: STATE_ALARM_ARMED_AWAY,
    OverkizCommandParam.DISARMED: STATE_ALARM_DISARMED,
    OverkizCommandParam.PARTIAL: STATE_ALARM_ARMED_NIGHT,
}


def _state_myfox_alarm_controller(
    select_state: Callable[[str], OverkizStateType],
) -> str:
    """Return the state of the device."""
    if (
        cast(str, select_state(OverkizState.CORE_INTRUSION))
        == OverkizCommandParam.DETECTED
    ):
        return STATE_ALARM_TRIGGERED

    return MAP_MYFOX_STATUS_STATE[
        cast(str, select_state(OverkizState.MYFOX_ALARM_STATUS))
    ]


MAP_ARM_TYPE: dict[str, str] = {
    OverkizCommandParam.DISARMED: STATE_ALARM_DISARMED,
    OverkizCommandParam.ARMED_DAY: STATE_ALARM_ARMED_HOME,
    OverkizCommandParam.ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
    OverkizCommandParam.ARMED: STATE_ALARM_ARMED_AWAY,
}


def _state_alarm_panel_controller(
    select_state: Callable[[str], OverkizStateType],
) -> str:
    """Return the state of the device."""
    return MAP_ARM_TYPE[
        cast(str, select_state(OverkizState.VERISURE_ALARM_PANEL_MAIN_ARM_TYPE))
    ]


ALARM_DESCRIPTIONS: list[OverkizAlarmDescription] = [
    # TSKAlarmController
    # Disabled by default since all Overkiz hubs have this
    # virtual device, but only a few users actually use this.
    OverkizAlarmDescription(
        key=UIWidget.TSKALARM_CONTROLLER,
        entity_registry_enabled_default=False,
        supported_features=(
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_NIGHT
            | AlarmControlPanelEntityFeature.TRIGGER
        ),
        fn_state=_state_tsk_alarm_controller,
        alarm_disarm=OverkizCommand.ALARM_OFF,
        alarm_arm_home=OverkizCommand.SET_TARGET_ALARM_MODE,
        alarm_arm_home_args=OverkizCommandParam.PARTIAL_1,
        alarm_arm_night=OverkizCommand.SET_TARGET_ALARM_MODE,
        alarm_arm_night_args=OverkizCommandParam.PARTIAL_2,
        alarm_arm_away=OverkizCommand.SET_TARGET_ALARM_MODE,
        alarm_arm_away_args=OverkizCommandParam.TOTAL,
        alarm_trigger=OverkizCommand.ALARM_ON,
    ),
    # StatefulAlarmController
    OverkizAlarmDescription(
        key=UIWidget.STATEFUL_ALARM_CONTROLLER,
        supported_features=(
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_NIGHT
        ),
        fn_state=_state_stateful_alarm_controller,
        alarm_disarm=OverkizCommand.ALARM_OFF,
        alarm_arm_home=OverkizCommand.ALARM_ZONE_ON,
        alarm_arm_home_args=OverkizCommandParam.A,
        alarm_arm_night=OverkizCommand.ALARM_ZONE_ON,
        alarm_arm_night_args=f"{OverkizCommandParam.A}, {OverkizCommandParam.B}",
        alarm_arm_away=OverkizCommand.ALARM_ZONE_ON,
        alarm_arm_away_args=(
            f"{OverkizCommandParam.A},{OverkizCommandParam.B},{OverkizCommandParam.C}"
        ),
    ),
    # MyFoxAlarmController
    OverkizAlarmDescription(
        key=UIWidget.MY_FOX_ALARM_CONTROLLER,
        supported_features=AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_NIGHT,
        fn_state=_state_myfox_alarm_controller,
        alarm_disarm=OverkizCommand.DISARM,
        alarm_arm_night=OverkizCommand.PARTIAL,
        alarm_arm_away=OverkizCommand.ARM,
    ),
    # AlarmPanelController
    OverkizAlarmDescription(
        key=UIWidget.ALARM_PANEL_CONTROLLER,
        supported_features=(
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_NIGHT
        ),
        fn_state=_state_alarm_panel_controller,
        alarm_disarm=OverkizCommand.DISARM,
        alarm_arm_home=OverkizCommand.ARM_PARTIAL_DAY,
        alarm_arm_night=OverkizCommand.ARM_PARTIAL_NIGHT,
        alarm_arm_away=OverkizCommand.ARM,
    ),
]

SUPPORTED_DEVICES = {description.key: description for description in ALARM_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Overkiz alarm control panel from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OverkizAlarmControlPanel(
            device.device_url,
            data.coordinator,
            description,
        )
        for device in data.platforms[Platform.ALARM_CONTROL_PANEL]
        if (
            description := SUPPORTED_DEVICES.get(device.widget)
            or SUPPORTED_DEVICES.get(device.ui_class)
        )
    )


class OverkizAlarmControlPanel(OverkizDescriptiveEntity, AlarmControlPanelEntity):
    """Representation of an Overkiz Alarm Control Panel."""

    entity_description: OverkizAlarmDescription

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator, description)

        self._attr_supported_features = self.entity_description.supported_features

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self.entity_description.fn_state(self.executor.select_state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        assert self.entity_description.alarm_disarm
        await self.async_execute_command(
            self.entity_description.alarm_disarm,
            self.entity_description.alarm_disarm_args,
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        assert self.entity_description.alarm_arm_home
        await self.async_execute_command(
            self.entity_description.alarm_arm_home,
            self.entity_description.alarm_arm_home_args,
        )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm night command."""
        assert self.entity_description.alarm_arm_night
        await self.async_execute_command(
            self.entity_description.alarm_arm_night,
            self.entity_description.alarm_arm_night_args,
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        assert self.entity_description.alarm_arm_away
        await self.async_execute_command(
            self.entity_description.alarm_arm_away,
            self.entity_description.alarm_arm_away_args,
        )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        assert self.entity_description.alarm_trigger
        await self.async_execute_command(
            self.entity_description.alarm_trigger,
            self.entity_description.alarm_trigger_args,
        )

    async def async_execute_command(self, command_name: str, args: Any) -> None:
        """Execute device command in async context."""
        if args:
            await self.executor.async_execute_command(command_name, args)
        else:
            await self.executor.async_execute_command(command_name)
