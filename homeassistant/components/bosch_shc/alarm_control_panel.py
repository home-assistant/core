"""Platform for alarm control panel integration."""
from __future__ import annotations

from boschshcpy import SHCIntrusionSystem, SHCSession

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_CUSTOM_BYPASS,
    SUPPORT_ALARM_ARM_HOME,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_CUSTOM_BYPASS,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DATA_SESSION, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm control panel platform."""
    entities = []
    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    intrusion_system = session.intrusion_system
    alarm_control_panel = IntrusionSystemAlarmControlPanel(
        device=intrusion_system,
        parent_id=session.information.unique_id,
        entry_id=config_entry.entry_id,
    )
    entities.append(alarm_control_panel)

    async_add_entities(entities)


class IntrusionSystemAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of SHC intrusion detection control."""

    _attr_icon: str = "mdi:security"
    _attr_code_arm_required: bool = False
    _attr_code_format: str | None = None
    _attr_should_poll = False
    _attr_supported_features: int = (
        SUPPORT_ALARM_ARM_AWAY
        | SUPPORT_ALARM_ARM_HOME
        | SUPPORT_ALARM_ARM_CUSTOM_BYPASS
    )

    def __init__(
        self, device: SHCIntrusionSystem, parent_id: str, entry_id: str
    ) -> None:
        """Initialize the generic SHC device."""
        self._device = device
        self._entry_id = entry_id
        self._attr_name = device.name
        self._attr_unique_id = device.id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer=device.manufacturer,
            model=device.device_model,
            name=device.name,
            via_device=(DOMAIN, parent_id),
        )

    async def async_added_to_hass(self):
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed():
            self.schedule_update_ha_state()

        self._device.subscribe_callback(self.entity_id, on_state_changed)

    async def async_will_remove_from_hass(self):
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        self._device.unsubscribe_callback(self.entity_id)

    @property
    def available(self):
        """Return false if status is unavailable."""
        return self._device.system_availability

    @property
    def state(self) -> StateType:
        """Return the state of the device."""
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMING:
            return STATE_ALARM_ARMING
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_DISARMED:
            return STATE_ALARM_DISARMED
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMED:
            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.FULL_PROTECTION
            ):
                return STATE_ALARM_ARMED_AWAY

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.PARTIAL_PROTECTION
            ):
                return STATE_ALARM_ARMED_HOME

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.CUSTOM_PROTECTION
            ):
                return STATE_ALARM_ARMED_CUSTOM_BYPASS
        return None

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.disarm()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.arm_full_protection()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.arm_partial_protection()

    def alarm_arm_custom_bypass(self, code=None):
        """Send arm home command."""
        self._device.arm_individual_protection()
