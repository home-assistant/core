"""Platform for alarm control panel integration."""

from typing import override

from boschshcpy import SHCIntrusionSystem

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BoschConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC alarm control panel platform."""
    session = config_entry.runtime_data
    async_add_entities(
        [
            IntrusionSystemAlarmControlPanel(
                hass=hass,
                device=session.intrusion_system,
                entry_id=config_entry.entry_id,
            )
        ]
    )


class IntrusionSystemAlarmControlPanel(AlarmControlPanelEntity):
    """Representation of the SHC intrusion detection system."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    _attr_code_format: CodeFormat | None = None
    _attr_code_arm_required = False
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_AWAY
        | AlarmControlPanelEntityFeature.ARM_HOME
        | AlarmControlPanelEntityFeature.ARM_CUSTOM_BYPASS
    )

    def __init__(
        self, hass: HomeAssistant, device: SHCIntrusionSystem, entry_id: str
    ) -> None:
        """Initialize the intrusion detection system."""
        self._device = device
        self._attr_unique_id = f"{device.root_device_id}_{device.id}"
        device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            translation_key="intrusion_system",
            manufacturer=device.manufacturer,
            model=device.device_model,
        )
        if device.root_device_id is not None and (
            hub := dr.async_get(hass).async_get_device_by_identifier(
                (DOMAIN, device.root_device_id), entry_id
            )
        ):
            device_info["via_device_id"] = hub.id
        self._attr_device_info = device_info

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to SHC events."""
        await super().async_added_to_hass()

        def on_state_changed() -> None:
            self.schedule_update_ha_state()

        self._device.subscribe_callback(self.entity_id, on_state_changed)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unsubscribe from SHC events."""
        await super().async_will_remove_from_hass()
        self._device.unsubscribe_callback(self.entity_id)

    @property
    @override
    def available(self) -> bool:
        """Return false if the system is unavailable."""
        return bool(self._device.system_availability)

    @property
    @override
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the state of the alarm system."""
        alarm = self._device.alarm_state
        if alarm in (
            SHCIntrusionSystem.AlarmState.ALARM_ON,
            SHCIntrusionSystem.AlarmState.ALARM_MUTED,
        ):
            return AlarmControlPanelState.TRIGGERED
        if alarm is SHCIntrusionSystem.AlarmState.PRE_ALARM:
            return AlarmControlPanelState.PENDING

        arming = self._device.arming_state
        if arming is SHCIntrusionSystem.ArmingState.SYSTEM_ARMING:
            return AlarmControlPanelState.ARMING
        if arming is SHCIntrusionSystem.ArmingState.SYSTEM_DISARMED:
            return AlarmControlPanelState.DISARMED

        profile = self._device.active_configuration_profile
        if profile is SHCIntrusionSystem.Profile.FULL_PROTECTION:
            return AlarmControlPanelState.ARMED_AWAY
        if profile is SHCIntrusionSystem.Profile.PARTIAL_PROTECTION:
            return AlarmControlPanelState.ARMED_HOME
        # Custom or unrecognized profiles must not be reported as unknown
        # while the system is armed.
        return AlarmControlPanelState.ARMED_CUSTOM_BYPASS

    @override
    def alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the system."""
        self._device.disarm()

    @override
    def alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the system with full protection."""
        self._device.arm_full_protection()

    @override
    def alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the system with partial protection."""
        self._device.arm_partial_protection()

    @override
    def alarm_arm_custom_bypass(self, code: str | None = None) -> None:
        """Arm the system with individual protection."""
        self._device.arm_individual_protection()
