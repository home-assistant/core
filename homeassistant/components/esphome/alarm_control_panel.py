"""Support for ESPHome Alarm Control Panel."""
from __future__ import annotations

from aioesphomeapi import (
    AlarmControlPanelCommand,
    AlarmControlPanelEntityState,
    AlarmControlPanelInfo,
    AlarmControlPanelState,
    APIIntEnum,
    EntityInfo,
)

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    CodeFormat,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMED_VACATION,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_DISARMING,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import EsphomeEntity, esphome_state_property, platform_async_setup_entry
from .enum_mapper import EsphomeEnumMapper

_ESPHOME_ACP_STATE_TO_HASS_STATE: EsphomeEnumMapper[
    AlarmControlPanelState, str
] = EsphomeEnumMapper(
    {
        AlarmControlPanelState.DISARMED: STATE_ALARM_DISARMED,
        AlarmControlPanelState.ARMED_HOME: STATE_ALARM_ARMED_HOME,
        AlarmControlPanelState.ARMED_AWAY: STATE_ALARM_ARMED_AWAY,
        AlarmControlPanelState.ARMED_NIGHT: STATE_ALARM_ARMED_NIGHT,
        AlarmControlPanelState.ARMED_VACATION: STATE_ALARM_ARMED_VACATION,
        AlarmControlPanelState.ARMED_CUSTOM_BYPASS: STATE_ALARM_ARMED_CUSTOM_BYPASS,
        AlarmControlPanelState.PENDING: STATE_ALARM_PENDING,
        AlarmControlPanelState.ARMING: STATE_ALARM_ARMING,
        AlarmControlPanelState.DISARMING: STATE_ALARM_DISARMING,
        AlarmControlPanelState.TRIGGERED: STATE_ALARM_TRIGGERED,
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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up ESPHome switches based on a config entry."""
    await platform_async_setup_entry(
        hass,
        entry,
        async_add_entities,
        info_type=AlarmControlPanelInfo,
        entity_type=EsphomeAlarmControlPanel,
        state_type=AlarmControlPanelEntityState,
    )


class EsphomeAlarmControlPanel(
    EsphomeEntity[AlarmControlPanelInfo, AlarmControlPanelEntityState],
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
    def state(self) -> str | None:
        """Return the state of the device."""
        return _ESPHOME_ACP_STATE_TO_HASS_STATE.from_esphome(self._state.state)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.DISARM, code
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_HOME, code
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_AWAY, code
        )

    async def async_alarm_arm_night(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_NIGHT, code
        )

    async def async_alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_CUSTOM_BYPASS, code
        )

    async def async_alarm_arm_vacation(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.ARM_VACATION, code
        )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send alarm trigger command."""
        await self._client.alarm_control_panel_command(
            self._key, AlarmControlPanelCommand.TRIGGER, code
        )
