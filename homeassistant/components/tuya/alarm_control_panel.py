"""Support for Tuya Alarm."""

from __future__ import annotations

from tuya_device_handlers.definition.alarm_control_panel import (
    TuyaAlarmControlPanelDefinition,
    get_default_definition,
)
from tuya_device_handlers.helpers.homeassistant import (
    TuyaAlarmControlPanelAction,
    TuyaAlarmControlPanelState,
)
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TuyaConfigEntry
from .const import TUYA_DISCOVERY_NEW, DeviceCategory, DPCode
from .entity import TuyaEntity

ALARM: dict[DeviceCategory, AlarmControlPanelEntityDescription] = {
    DeviceCategory.MAL: AlarmControlPanelEntityDescription(
        key=DPCode.MASTER_MODE,
        name="Alarm",
    ),
    DeviceCategory.WG2: AlarmControlPanelEntityDescription(
        key=DPCode.MASTER_MODE,
        name="Alarm",
    ),
}

_TUYA_TO_HA_STATE_MAPPINGS = {
    TuyaAlarmControlPanelState.DISARMED: AlarmControlPanelState.DISARMED,
    TuyaAlarmControlPanelState.ARMED_HOME: AlarmControlPanelState.ARMED_HOME,
    TuyaAlarmControlPanelState.ARMED_AWAY: AlarmControlPanelState.ARMED_AWAY,
    TuyaAlarmControlPanelState.ARMED_NIGHT: AlarmControlPanelState.ARMED_NIGHT,
    TuyaAlarmControlPanelState.ARMED_VACATION: AlarmControlPanelState.ARMED_VACATION,
    TuyaAlarmControlPanelState.ARMED_CUSTOM_BYPASS: AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
    TuyaAlarmControlPanelState.PENDING: AlarmControlPanelState.PENDING,
    TuyaAlarmControlPanelState.ARMING: AlarmControlPanelState.ARMING,
    TuyaAlarmControlPanelState.DISARMING: AlarmControlPanelState.DISARMING,
    TuyaAlarmControlPanelState.TRIGGERED: AlarmControlPanelState.TRIGGERED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TuyaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tuya alarm dynamically through Tuya discovery."""
    manager = entry.runtime_data.manager

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Tuya siren."""
        entities: list[TuyaAlarmEntity] = []
        for device_id in device_ids:
            device = manager.device_map[device_id]
            if (description := ALARM.get(device.category)) and (
                definition := get_default_definition(device)
            ):
                entities.append(
                    TuyaAlarmEntity(device, manager, description, definition)
                )
        async_add_entities(entities)

    async_discover_device([*manager.device_map])

    entry.async_on_unload(
        async_dispatcher_connect(hass, TUYA_DISCOVERY_NEW, async_discover_device)
    )


class TuyaAlarmEntity(TuyaEntity, AlarmControlPanelEntity):
    """Tuya Alarm Entity."""

    _attr_name = None
    _attr_code_arm_required = False

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: AlarmControlPanelEntityDescription,
        definition: TuyaAlarmControlPanelDefinition,
    ) -> None:
        """Init Tuya Alarm."""
        super().__init__(device, device_manager, description)
        self._action_wrapper = definition.action_wrapper
        self._changed_by_wrapper = definition.changed_by_wrapper
        self._state_wrapper = definition.state_wrapper

        # Determine supported modes
        if TuyaAlarmControlPanelAction.ARM_HOME in definition.action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_HOME
        if TuyaAlarmControlPanelAction.ARM_AWAY in definition.action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.ARM_AWAY
        if TuyaAlarmControlPanelAction.TRIGGER in definition.action_wrapper.options:
            self._attr_supported_features |= AlarmControlPanelEntityFeature.TRIGGER

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the device."""
        tuya_value = self._read_wrapper(self._state_wrapper)
        return _TUYA_TO_HA_STATE_MAPPINGS.get(tuya_value) if tuya_value else None

    @property
    def changed_by(self) -> str | None:
        """Last change triggered by."""
        return self._read_wrapper(self._changed_by_wrapper)

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send Disarm command."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaAlarmControlPanelAction.DISARM
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send Home command."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaAlarmControlPanelAction.ARM_HOME
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send Arm command."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaAlarmControlPanelAction.ARM_AWAY
        )

    async def async_alarm_trigger(self, code: str | None = None) -> None:
        """Send SOS command."""
        await self._async_send_wrapper_updates(
            self._action_wrapper, TuyaAlarmControlPanelAction.TRIGGER
        )
