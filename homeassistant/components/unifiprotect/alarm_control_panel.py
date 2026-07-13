"""Support for UniFi Protect NVR alarm control panel."""

from typing import cast, override

from uiprotect.data import NVR, NvrArmModeStatus
from uiprotect.exceptions import GlobalAlarmManagerError

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_BRAND, DOMAIN
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectNVREntity
from .utils import _async_unifi_mac_from_hass, async_ufp_instance_command

PARALLEL_UPDATES = 0

_UIPROTECT_TO_HA: dict[NvrArmModeStatus, AlarmControlPanelState] = {
    NvrArmModeStatus.DISABLED: AlarmControlPanelState.DISARMED,
    NvrArmModeStatus.ARMING: AlarmControlPanelState.ARMING,
    NvrArmModeStatus.ARMED: AlarmControlPanelState.ARMED_AWAY,
    NvrArmModeStatus.BREACH: AlarmControlPanelState.TRIGGERED,
    NvrArmModeStatus.UNKNOWN: AlarmControlPanelState.DISARMED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up alarm control panel for UniFi Protect NVR."""
    data = entry.runtime_data
    api = data.api

    # No public Integration API available (e.g. older NVR firmware that does
    # not expose the Alarm Manager endpoint, or no API key configured).
    # Skip entity creation entirely; we cannot represent the alarm state.
    if not api.has_public_bootstrap:
        return

    # ``arm_mode`` is ``None`` on NVR firmware that predates the Alarm Manager
    # public API. Skip entity creation so the user does not see a permanently
    # unavailable entity.
    if api.public_bootstrap.arm_mode is None:
        return

    # In public-API-only mode there is no private bootstrap; the NVR device is
    # the public one, whose mac the library backfills during priming.
    if api.is_public_only:
        public_nvr = api.public_bootstrap.nvr
        if public_nvr is None:
            return
        nvr = cast(NVR, public_nvr)
    else:
        nvr = api.bootstrap.nvr
    async_add_entities([ProtectNVRAlarmControlPanel(data, device=nvr)])


class ProtectNVRAlarmControlPanel(ProtectNVREntity, AlarmControlPanelEntity):
    """UniFi Protect NVR Alarm Control Panel."""

    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_translation_key = "nvr_alarm"
    _state_attrs = ("_attr_available", "_attr_alarm_state")

    def __init__(self, data: ProtectData, device: NVR) -> None:
        """Initialize the alarm control panel."""
        super().__init__(data, device, EntityDescription(key="alarm"))
        self._refresh_alarm_state()

    @callback
    @override
    def _async_set_device_info(self) -> None:
        if not self.data.api.is_public_only:
            super()._async_set_device_info()
            return
        # Degraded: no market name or console URL, and ``type`` only on
        # newer firmware. The mac is backfilled by the library, matching the
        # device created at setup.
        mac = _async_unifi_mac_from_hass(self.device.mac)
        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
            identifiers={(DOMAIN, mac)},
            manufacturer=DEFAULT_BRAND,
            name=self.device.display_name,
            model=self.device.type,
        )

    @callback
    def _refresh_alarm_state(self) -> None:
        """Update _attr_alarm_state from the public bootstrap cache."""
        api = self.data.api
        arm_mode = api.public_bootstrap.arm_mode if api.has_public_bootstrap else None
        if arm_mode is None:
            # No alarm data available — force unavailable regardless of the
            # websocket state managed by the base class.
            self._attr_available = False
            self._attr_alarm_state = None
            return
        # arm_mode is delivered over the public devices websocket, so
        # availability tracks the public WS health (like relay/siren), not the
        # private connection the base class would otherwise apply for the NVR.
        self._attr_available = self.data.last_public_update_success
        # Fall back to DISARMED for unknown future status values rather than
        # rendering the entity as ``unknown``.
        self._attr_alarm_state = _UIPROTECT_TO_HA.get(
            arm_mode.status, AlarmControlPanelState.DISARMED
        )

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._refresh_alarm_state()

    @async_ufp_instance_command
    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        try:
            await self.data.api.disable_arm_alarm_public()
        except GlobalAlarmManagerError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="global_alarm_manager",
            ) from err

    @async_ufp_instance_command
    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command (arms with the currently selected profile)."""
        try:
            await self.data.api.enable_arm_alarm_public()
        except GlobalAlarmManagerError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="global_alarm_manager",
            ) from err
