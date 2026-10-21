"""Support for Imou alarm control panel entities."""

import logging
from typing import override

from pyimouapi.const import PARAM_MODE, PARAM_STATE, PARAM_SUPPORTED
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityDescription,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity
from .helpers import async_wrap_imou_command

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

_ARM_MODES = frozenset({"home", "away"})

_MODE_TO_STATE = {
    "home": AlarmControlPanelState.ARMED_HOME,
    "away": AlarmControlPanelState.ARMED_AWAY,
    "disarm": AlarmControlPanelState.DISARMED,
}

ALARM_PANEL_DESCRIPTION = AlarmControlPanelEntityDescription(
    key=PARAM_MODE,
    translation_key="alarm",
    name=None,
)


def _device_has_alarm_panel(device: ImouHaDevice) -> bool:
    """Return whether the device exposes a usable arming panel."""
    panel = device.alarm_control_panel
    if panel is None:
        return False
    supported = panel.get(PARAM_SUPPORTED, [])
    if not isinstance(supported, list):
        return False
    modes = {mode for mode in supported if isinstance(mode, str)}
    if "disarm" not in modes:
        return False
    return bool(modes & _ARM_MODES)


def _iter_alarm_control_panels(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[AlarmControlPanelEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for devices with an arming panel."""
    return [
        (ALARM_PANEL_DESCRIPTION, device)
        for device in coordinator.devices
        if _device_has_alarm_panel(device)
    ]


def _supported_features(panel: dict) -> AlarmControlPanelEntityFeature:
    """Return arm features supported by the device panel."""
    supported = panel.get(PARAM_SUPPORTED, [])
    features = AlarmControlPanelEntityFeature(0)
    if "home" in supported:
        features |= AlarmControlPanelEntityFeature.ARM_HOME
    if "away" in supported:
        features |= AlarmControlPanelEntityFeature.ARM_AWAY
    return features


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou alarm control panel entities."""
    coordinator = entry.runtime_data

    def _add_alarm_panels(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouAlarmControlPanel(coordinator, description, device)
            for description, device in _iter_alarm_control_panels(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_alarm_panels))
    _add_alarm_panels(coordinator.devices)


class ImouAlarmControlPanel(ImouEntity, AlarmControlPanelEntity):
    """Imou alarm control panel entity."""

    entity_description: AlarmControlPanelEntityDescription
    _attr_code_arm_required = False

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        description: AlarmControlPanelEntityDescription,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the Imou alarm control panel entity."""
        super().__init__(coordinator, description, device)
        panel = device.alarm_control_panel
        assert panel is not None
        self._attr_supported_features = _supported_features(panel)

    @property
    @override
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current arming state."""
        panel = self.device.alarm_control_panel
        assert panel is not None
        mode = panel.get(PARAM_STATE)
        if not isinstance(mode, str):
            return None
        mapped = _MODE_TO_STATE.get(mode)
        if mapped is None:
            _LOGGER.debug("Unknown alarm mode %r for %s", mode, self._device_key)
            return None
        return mapped

    @override
    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm the device in home mode."""
        await self._async_set_mode("home")

    @override
    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm the device in away mode."""
        await self._async_set_mode("away")

    @override
    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm the device."""
        await self._async_set_mode("disarm")

    @async_wrap_imou_command("alarm_arm_disarm_failed")
    async def _async_set_mode(self, mode: str) -> None:
        """Call the vendor library to change arming mode."""
        await self.coordinator.device_manager.async_set_alarm_mode(self.device, mode)
        await self.coordinator.async_request_refresh()
