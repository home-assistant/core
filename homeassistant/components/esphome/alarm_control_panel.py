"""Support for ESPHome Alarm Control Panel."""

from __future__ import annotations

from functools import partial

from aioesphomeapi import (
    AlarmControlPanelCommand,
    AlarmControlPanelEntityState as ESPHomeAlarmControlPanelEntityState,
    AlarmControlPanelInfo,
    AlarmControlPanelState as ESPHomeAlarmControlPanelState,
    APIIntEnum,
    EntityInfo,
)

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import callback

from .entity import (
    EsphomeEntity,
    convert_api_error_ha_error,
    esphome_state_property,
    platform_async_setup_entry,
)
from .enum_mapper import EsphomeEnumMapper

_ESPHOME_ACP_STATE_TO_HASS_STATE: EsphomeEnumMapper[
    ESPHomeAlarmControlPanelState, AlarmControlPanelState
] = EsphomeEnumMapper(
    {
        ESPHomeAlarmControlPanelState.DISARMED: AlarmControlPanelState.DISARMED,
        ESPHomeAlarmControlPanelState.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
        ESPHomeAlarmControlPanelState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
        ESPHomeAlarmControlPanelState.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
        ESPHomeAlarmControlPanelState.ARMED_VACATION: AlarmControlPanelState.ARMED_VACATION,
        ESPHomeAlarmControlPanelState.ARMED_CUSTOM_BYPASS: AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
        ESPHomeAlarmControlPanelState.PENDING: AlarmControlPanelState.PENDING,
        ESPHomeAlarmControlPanelState.ARMING: AlarmControlPanelState.ARMING,
        ESPHomeAlarmControlPanelState.DISARMING: AlarmControlPanelState.DISARMING,
        ESPHomeAlarmControlPanelState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
    }
)


class EspHomeACPFeatures(APIIntEnum):
    """ESPHome AlarmCintolPanel feature numbers."""

    ARM_HOME = 1
    ARM_AWAY = 2
    ARM_NIGHT = 4
    TRIGGER = 8
    ARM_CUSTOM_BYPASS = 16
    ARM_VACATION = 32


class EsphomeAlarmControlPanel(
    EsphomeEntity[AlarmControlPanelInfo, ESPHomeAlarmControlPanelEntityState],
    AlarmControlPanelEntity,
):
    """An Alarm Control Panel implementation for ESPHome."""

    @callback
    def _on_static_info_update(self, static_info: EntityInfo) -> None:
        """Set attrs from static info."""
        super()._on_static_info_update(static_info)
        static_info = self._static_info
        feature = 0
        if static_info.supported_features & EspHomeACPFeatures.ARM_HOME:
            feature |= AlarmControlPanelEntityFeature.ARM_HOME
        if static_info.supported_features & EspHomeACPFeatures.ARM_AWAY:
            feature |= AlarmControlPanelEntityFeature.ARM_AWAY
        if static_info.supported_features & EspHomeACPFeatures.ARM_NIGHT:
            feature |= AlarmControlPanelEntityFeature.ARM_NIGHT
        if static_info.supported_features & EspHomeACPFeatures.TRIGGER:
            feature |= AlarmControlPanelEntityFeature.TRIGGER
        if static_info.supported_features & EspHomeACPFeatures.ARM_CUSTOM_BYPASS:
            feature |= AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        if static_info.supported_features & EspHomeACPFeatures.ARM_VACATION:
            feature |= AlarmControlPanelEntityFeature.ARM_VACATION
        self._attr_supported_features = AlarmControlPanelEntityFeature(feature)
        self._attr_code_format = (
            CodeFormat.NUMBER if static_info.requires_code else None
        )
        self._attr_code_arm_required = bool(static_info.requires_code_to_arm)

    @property
    @esphome_state_property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        return _ESPHOME_ACP_STATE_TO_HASS_STATE.from_esphome(self._state.state)

    @convert_api_error_ha_error
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.DISARM, code
        )

    @convert_api_error_ha_error
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_HOME, code
        )

    @convert_api_error_ha_error
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_AWAY, code
        )

    @convert_api_error_ha_error
    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_NIGHT, code
        )

    @convert_api_error_ha_error
    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_CUSTOM_BYPASS, code
        )

    @convert_api_error_ha_error
    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm away command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_VACATION, code
        )

    @convert_api_error_ha_error
    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.TRIGGER, code
        )


async_setup_entry = partial(
    platform_async_setup_entry,
    info_type=AlarmControlPanelInfo,
    entity_type=EsphomeAlarmControlPanel,
    state_type=ESPHomeAlarmControlPanelEntityState,
)
