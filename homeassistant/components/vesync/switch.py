"""Support for VeSync switches."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, Final

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_outlet, is_wall_switch, rgetattr
from .const import DOMAIN, VS_COORDINATOR, VS_DEVICES, VS_DISCOVERY, VS_MANAGER
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class VeSyncSwitchEntityDescription(SwitchEntityDescription):
    """A class that describes custom switch entities."""

    is_on: Callable[[VeSyncBaseDevice], bool]
    exists_fn: Callable[[VeSyncBaseDevice], bool]
    on_fn: Callable[[VeSyncBaseDevice], bool]
    off_fn: Callable[[VeSyncBaseDevice], bool]


SENSOR_DESCRIPTIONS: Final[tuple[VeSyncSwitchEntityDescription, ...]] = (
    VeSyncSwitchEntityDescription(
        key="device_status",
        is_on=lambda device: device.state.device_status == "on",
        # Other types of wall switches support dimming.  Those use light.py platform.
        exists_fn=lambda device: is_wall_switch(device) or is_outlet(device),
        name=None,
        on_fn=lambda device: device.turn_on(),
        off_fn=lambda device: device.turn_off(),
    ),
    VeSyncSwitchEntityDescription(
        key="display",
        is_on=lambda device: device.state.display_status,
        exists_fn=lambda device: rgetattr(device, "state.display_status") is not None,
        translation_key="display",
        on_fn=lambda device: device.turn_on_display(),
        off_fn=lambda device: device.turn_off_display(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(
        hass.data[DOMAIN][VS_MANAGER].devices, async_add_entities, coordinator
    )


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: VeSyncDataCoordinator,
):
    """Check if device is online and add entity."""
    async_add_entities(
        VeSyncSwitchEntity(dev, description, coordinator)
        for dev in devices
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncSwitchEntity(SwitchEntity, VeSyncBaseEntity):
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
        if not self.entity_description.off_fn(self.device):
            raise HomeAssistantError("An error occurred while turning off.")

        self.schedule_update_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        if not self.entity_description.on_fn(self.device):
            raise HomeAssistantError("An error occurred while turning on.")

        self.schedule_update_ha_state()
