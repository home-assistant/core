"""Platform for alarm control panel integration."""

from boschshcpy import SHCIntrusionSystem, SHCSession
from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.const import (
    Platform,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DATA_SESSION, DOMAIN
from .entity import async_migrate_to_new_unique_id

PARALLEL_UPDATES = 1


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the alarm control panel platform."""
    devices = []

    session: SHCSession = hass.data[DOMAIN][config_entry.entry_id][DATA_SESSION]

    intrusion_system = session.intrusion_system
    await async_migrate_to_new_unique_id(
        hass,
        Platform.ALARM_CONTROL_PANEL,
        device=intrusion_system,
        attr_name=None,
        old_unique_id=f"{config_entry.entry_id}_{intrusion_system.id}",
    )
    alarm_control_panel = IntrusionSystemAlarmControlPanel(
        device=intrusion_system,
        entry_id=config_entry.entry_id,
    )
    devices.append(alarm_control_panel)

    async_add_entities(devices)


class IntrusionSystemAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of SHC intrusion detection control."""

    _attr_has_entity_name = True
    _attr_name = None  # primary entity — HA uses the device name as the entity name

    def __init__(self, device: SHCIntrusionSystem, entry_id: str):
        """Initialize the intrusion detection control."""
        self._device = device
        self._entry_id = entry_id
        self._attr_unique_id = f"{self._device.root_device_id}_{self._device.id}"

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
    def device_id(self):
        """Return the ID of the system."""
        return self._device.id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self._device.name,
            manufacturer=self._device.manufacturer,
            model=self._device.device_model,
            via_device=(DOMAIN, self._device.root_device_id),
        )

    @property
    def available(self):
        """Return false if status is unavailable."""
        return self._device.system_availability

    @property
    def should_poll(self):
        """Report polling mode. System is communicating via long polling."""
        return False

    @property
    def alarm_state(self):
        """Return the state of the device."""
        if self._device.alarm_state == SHCIntrusionSystem.AlarmState.ALARM_ON:
            return AlarmControlPanelState.TRIGGERED
        if self._device.alarm_state == SHCIntrusionSystem.AlarmState.ALARM_MUTED:
            return AlarmControlPanelState.TRIGGERED
        if self._device.alarm_state == SHCIntrusionSystem.AlarmState.PRE_ALARM:
            return AlarmControlPanelState.PENDING

        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMING:
            return AlarmControlPanelState.ARMING
        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_DISARMED:
            return AlarmControlPanelState.DISARMED

        if self._device.arming_state == SHCIntrusionSystem.ArmingState.SYSTEM_ARMED:
            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.FULL_PROTECTION
            ):
                return AlarmControlPanelState.ARMED_AWAY

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.PARTIAL_PROTECTION
            ):
                return AlarmControlPanelState.ARMED_HOME

            if (
                self._device.active_configuration_profile
                == SHCIntrusionSystem.Profile.CUSTOM_PROTECTION
            ):
                return AlarmControlPanelState.ARMED_CUSTOM_BYPASS
        return None

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return (
            AlarmControlPanelEntityFeature.ARM_AWAY
            | AlarmControlPanelEntityFeature.ARM_HOME
            | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
        )

    @property
    def manufacturer(self):
        """Return manufacturer of the device."""
        return self._device.manufacturer

    @property
    def code_format(self):
        """Return the regex for code format or None if no code is required."""
        return None
        # return FORMAT_NUMBER

    @property
    def code_arm_required(self):
        """Whether the code is required for arm actions."""
        return False

    async def async_alarm_disarm(self, code=None):
        """Send disarm command."""
        await self._device.async_disarm()

    async def async_alarm_arm_away(self, code=None):
        """Send arm away command."""
        await self._device.async_arm_full_protection()

    async def async_alarm_arm_home(self, code=None):
        """Send arm home command."""
        await self._device.async_arm_partial_protection()

    async def async_alarm_arm_custom_bypass(self, code=None):
        """Send arm home command."""
        await self._device.async_arm_individual_protection()

    async def async_alarm_mute(self):
        """Mute alarm command."""
        await self._device.async_mute()

    @property
    def extra_state_attributes(self):
        """Return additional IDS state attributes.

        Exposes alarm_state_incidents, security_gaps, and remaining_time_until_armed
        from the SHCIntrusionSystem domain model.
        """
        return {
            "incidents": self._device.alarm_state_incidents,
            "security_gaps": self._device.security_gaps,
            "remaining_time_until_armed": self._device.remaining_time_until_armed,
        }
