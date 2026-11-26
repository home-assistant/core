"""Support for UniFi Protect NVR alarm control panel."""

from collections.abc import Collection
from typing import cast, override

from uiprotect.data import (
    NVR,
    ExternalArmProfile,
    ExternalArmProfileState,
    NvrArmModeStatus,
)
from uiprotect.exceptions import GlobalAlarmManagerError

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .data import ProtectData, ProtectDeviceType, UFPConfigEntry
from .entity import ProtectNVREntity
from .utils import async_ufp_instance_command

PARALLEL_UPDATES = 0

_NVR_ALARM_KEY = "alarm"
_PROFILE_KEY_PREFIX = "arm_profile_"

_UIPROTECT_TO_HA: dict[NvrArmModeStatus, AlarmControlPanelState] = {
    NvrArmModeStatus.DISABLED: AlarmControlPanelState.DISARMED,
    NvrArmModeStatus.ARMING: AlarmControlPanelState.ARMING,
    NvrArmModeStatus.ARMED: AlarmControlPanelState.ARMED_AWAY,
    NvrArmModeStatus.BREACH: AlarmControlPanelState.TRIGGERED,
    NvrArmModeStatus.UNKNOWN: AlarmControlPanelState.DISARMED,
}

_EXTERNAL_TO_HA: dict[ExternalArmProfileState, AlarmControlPanelState] = {
    ExternalArmProfileState.DISARMED: AlarmControlPanelState.DISARMED,
    ExternalArmProfileState.ARMING: AlarmControlPanelState.ARMING,
    ExternalArmProfileState.ARMED: AlarmControlPanelState.ARMED_AWAY,
    ExternalArmProfileState.BREACHING: AlarmControlPanelState.PENDING,
    ExternalArmProfileState.BREACHED: AlarmControlPanelState.TRIGGERED,
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

    # In public-API-only mode there is no private bootstrap; the NVR device is
    # the public one, whose mac the library backfills during priming. Setup
    # guarantees it is present (it aborts with ConfigEntryNotReady otherwise).
    if api.is_public_only:
        nvr = cast(NVR, api.public_bootstrap.nvr)
    else:
        nvr = api.bootstrap.nvr

    external = api.public_bootstrap.uses_external_alarm_manager is True
    reload_requested = False

    @callback
    def _async_reload_on_mode_change(_: ProtectDeviceType) -> None:
        """Reload when the console switches between its alarm managers."""
        nonlocal reload_requested
        if (
            reload_requested
            or (api.public_bootstrap.uses_external_alarm_manager is True) is external
        ):
            return
        reload_requested = True
        # Deferred: the unload stops the websocket whose frame is being handled.
        hass.loop.call_soon(hass.config_entries.async_schedule_reload, entry.entry_id)

    entry.async_on_unload(data.async_subscribe(nvr.mac, _async_reload_on_mode_change))

    entity_registry = er.async_get(hass)
    unique_id_prefix = f"{nvr.mac}_{_PROFILE_KEY_PREFIX}"

    @callback
    def _async_remove_profile_panels(keep: Collection[str]) -> None:
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if (
                entity_entry.domain == ALARM_CONTROL_PANEL_DOMAIN
                and entity_entry.unique_id.startswith(unique_id_prefix)
                and entity_entry.unique_id.removeprefix(unique_id_prefix) not in keep
            ):
                entity_registry.async_remove(entity_entry.entity_id)

    if not external:
        if api.public_bootstrap.uses_external_alarm_manager is False:
            _async_remove_profile_panels(())
        # ``arm_mode`` is ``None`` on NVR firmware that predates the Alarm Manager
        # public API. Skip entity creation so the user does not see a permanently
        # unavailable entity.
        if api.public_bootstrap.arm_mode is not None:
            async_add_entities([ProtectNVRAlarmControlPanel(data, device=nvr)])
        return

    # The external alarm manager rejects the NVR panel's commands.
    if entity_id := entity_registry.async_get_entity_id(
        ALARM_CONTROL_PANEL_DOMAIN, DOMAIN, f"{nvr.mac}_{_NVR_ALARM_KEY}"
    ):
        entity_registry.async_remove(entity_id)

    known_profile_ids: set[str] = set()

    @callback
    def _async_sync_profiles() -> None:
        """Add panels for new profiles and remove those of deleted ones."""
        profiles = api.public_bootstrap.external_arm_profiles
        live = api.is_external_arm_profiles_live
        if live:
            known_profile_ids.intersection_update(profiles)
        if new_profile_ids := profiles.keys() - known_profile_ids:
            known_profile_ids.update(new_profile_ids)
            async_add_entities(
                ProtectExternalArmProfileAlarmControlPanel(
                    data, nvr, profiles[profile_id]
                )
                for profile_id in new_profile_ids
            )
        # Only a live list is complete; a failed fetch leaves it empty.
        if live:
            _async_remove_profile_panels(profiles)

    _async_sync_profiles()
    entry.async_on_unload(
        async_dispatcher_connect(hass, data.external_arm_signal, _async_sync_profiles)
    )


class ProtectNVRAlarmControlPanel(ProtectNVREntity, AlarmControlPanelEntity):
    """UniFi Protect NVR Alarm Control Panel."""

    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _attr_translation_key = "nvr_alarm"
    _state_attrs = ("_attr_available", "_attr_alarm_state")

    def __init__(self, data: ProtectData, device: NVR) -> None:
        """Initialize the alarm control panel."""
        super().__init__(data, device, EntityDescription(key=_NVR_ALARM_KEY))
        self._refresh_alarm_state()

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
        # availability tracks the public WS health, not the private connection
        # the base class would otherwise apply for the NVR. The NVR carries no
        # device state, so there is nothing else to gate on.
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


class ProtectExternalArmProfileAlarmControlPanel(
    ProtectNVREntity, AlarmControlPanelEntity
):
    """Arm profile of the external alarm manager."""

    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY
    _state_attrs = ("_attr_available", "_attr_alarm_state", "_attr_name")

    def __init__(
        self, data: ProtectData, device: NVR, profile: ExternalArmProfile
    ) -> None:
        """Initialize the alarm control panel."""
        self._profile_id = profile.id
        super().__init__(
            data, device, EntityDescription(key=f"{_PROFILE_KEY_PREFIX}{profile.id}")
        )
        self._refresh_alarm_state()

    @callback
    def _refresh_alarm_state(self) -> None:
        """Update the state from the external arm profile in the public bootstrap."""
        api = self.data.api
        if (
            not api.has_public_bootstrap
            or (
                profile := api.public_bootstrap.external_arm_profiles.get(
                    self._profile_id
                )
            )
            is None
        ):
            self._attr_available = False
            return
        # Without the profile websocket the state can be minutes old.
        self._attr_available = api.is_external_arm_profiles_live
        self._attr_name = profile.title
        self._attr_alarm_state = _EXTERNAL_TO_HA.get(profile.state)

    @callback
    @override
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        self._refresh_alarm_state()

    @callback
    def _async_profile_changed(self) -> None:
        self._async_updated_event(self.device)

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to the external arm profile updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.data.external_arm_signal, self._async_profile_changed
            )
        )

    @async_ufp_instance_command
    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the profile."""
        await self.data.api.disarm_external_arm_profile_public(self._profile_id)

    @async_ufp_instance_command
    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the profile."""
        await self.data.api.arm_external_arm_profile_public(self._profile_id)
