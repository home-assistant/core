"""Support for VeSync switches."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from pyvesync.base_devices import VeSyncBaseDevice, VeSyncHumidifier
from pyvesync.device_container import DeviceContainer

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_outlet, is_wall_switch, rgetattr
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


def _toggle_switch(device: VeSyncBaseDevice, *args) -> Awaitable[bool]:
    """Toggle power on."""
    if args and args[0] is True and hasattr(device, "turn_on"):
        return device.turn_on()
    if args and args[0] is False and hasattr(device, "turn_off"):
        return device.turn_off()
    raise HomeAssistantError("Device does not support toggling power.")


def _toggle_display(device: VeSyncBaseDevice, *args) -> Awaitable[bool]:
    """Toggle display on."""
    if hasattr(device, "toggle_display"):
        return device.toggle_display(*args)
    raise HomeAssistantError("Device does not support toggling display.")


def _toggle_child_lock(device: VeSyncBaseDevice, *args) -> Awaitable[bool]:
    """Toggle child lock on."""
    if hasattr(device, "toggle_child_lock"):
        return device.toggle_child_lock(*args)
    raise HomeAssistantError("Device does not support toggling child lock.")


def _toggle_auto_stop(device: VeSyncBaseDevice, *args) -> Awaitable[bool]:
    """Toggle automatic stop on."""
    match device:
        case VeSyncHumidifier() as sw if hasattr(sw, "toggle_automatic_stop"):
            return sw.toggle_automatic_stop(*args)
        case _:
            raise HomeAssistantError("Device does not support toggling automatic stop.")


@dataclass(frozen=True, kw_only=True)
class VeSyncSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes custom switch entities."""

    is_on: Callable[[VeSyncBaseDevice], bool]
    exists_fn: Callable[[VeSyncBaseDevice], bool]
    on_fn: Callable[[VeSyncBaseDevice], Awaitable[bool]]
    off_fn: Callable[[VeSyncBaseDevice], Awaitable[bool]]


SENSOR_DESCRIPTIONS: Final[tuple[VeSyncSwitchEntityDescription, ...]] = (
    VeSyncSwitchEntityDescription(
        key="device_status",
        is_on=lambda device: device.state.device_status == "on",
        # Other types of wall switches support dimming.  Those use light.py platform.
        exists_fn=lambda device: is_wall_switch(device) or is_outlet(device),
        name=None,
        on_fn=lambda device: _toggle_switch(device, True),
        off_fn=lambda device: _toggle_switch(device, False),
    ),
    VeSyncSwitchEntityDescription(
        key="display",
        is_on=lambda device: device.state.display_set_status == "on",
        exists_fn=(
            lambda device: rgetattr(device, "state.display_set_status") is not None
        ),
        translation_key="display",
        on_fn=lambda device: _toggle_display(device, True),
        off_fn=lambda device: _toggle_display(device, False),
    ),
    VeSyncSwitchEntityDescription(
        key="child_lock",
        is_on=lambda device: device.state.child_lock,
        exists_fn=(lambda device: rgetattr(device, "state.child_lock") is not None),
        translation_key="child_lock",
        on_fn=lambda device: _toggle_child_lock(device, True),
        off_fn=lambda device: _toggle_child_lock(device, False),
    ),
    VeSyncSwitchEntityDescription(
        key="auto_off_config",
        is_on=lambda device: device.state.automatic_stop_config,
        exists_fn=(
            lambda device: rgetattr(device, "state.automatic_stop_config") is not None
        ),
        translation_key="auto_off_config",
        on_fn=lambda device: _toggle_auto_stop(device, True),
        off_fn=lambda device: _toggle_auto_stop(device, False),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch platform."""

    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: DeviceContainer) -> None:
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        config_entry.runtime_data.manager.devices,
        async_add_entities,
        coordinator,
    )


@callback
def _setup_entities(
    devices: DeviceContainer,
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Check if device is online and add entity."""
    async_add_entities(
        VeSyncSwitchEntity(dev, description, coordinator)
        for dev in devices
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncSwitchEntity(SwitchEntity, VeSyncBaseEntity[VeSyncBaseDevice]):
    """VeSync switch entity class."""

    entity_description: VeSyncSwitchEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncSwitchEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"
        if is_outlet(self.device):
            self._attr_device_class = SwitchDeviceClass.OUTLET
        elif is_wall_switch(self.device):
            self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool | None:
        """Return the entity value to represent the entity state."""
        return self.entity_description.is_on(self.device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        if not await self.entity_description.off_fn(self.device):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Unknown error turning off device, no response.")

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if not await self.entity_description.on_fn(self.device):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Unknown error turning on device, no response.")

        self.async_write_ha_state()
