"""Support for VeSync button entities."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.device_container import DeviceContainer

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import supports_timer
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VeSyncButtonEntityDescription(ButtonEntityDescription):
    """Describe a VeSync button entity."""

    exists_fn: Callable[[VeSyncBaseDevice], bool]
    press_fn: Callable[[VeSyncBaseDevice], Awaitable[None]]


async def _clear_timer(device: VeSyncBaseDevice) -> None:
    """Clear the device timer."""
    if not supports_timer(device):
        raise HomeAssistantError("Device does not support timer adjustment.")
    try:
        timer_is_cleared = await device.clear_timer()
    except Exception as e:
        _LOGGER.error("Failed to clear timer: %s", e)
        raise HomeAssistantError(f"Failed to clear timer: {e}") from e
    if not timer_is_cleared:
        raise HomeAssistantError("Failed to clear timer: Unknown error.")


BUTTON_DESCRIPTIONS: tuple[VeSyncButtonEntityDescription, ...] = (
    VeSyncButtonEntityDescription(
        key="clear_timer",
        translation_key="clear_timer",
        exists_fn=supports_timer,
        press_fn=_clear_timer,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up VeSync button entities."""
    coordinator = config_entry.runtime_data

    @callback
    def discover(devices: list[VeSyncBaseDevice]) -> None:
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
    devices: DeviceContainer | list[VeSyncBaseDevice],
    async_add_entities: AddConfigEntryEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
) -> None:
    """Add button entities."""
    async_add_entities(
        VeSyncButtonEntity(dev, description, coordinator)
        for dev in devices
        for description in BUTTON_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncButtonEntity(VeSyncBaseEntity[VeSyncBaseDevice], ButtonEntity):
    """Representation of a VeSync button entity."""

    entity_description: VeSyncButtonEntityDescription

    def __init__(
        self,
        device: VeSyncBaseDevice,
        description: VeSyncButtonEntityDescription,
        coordinator: VeSyncDataCoordinator,
    ) -> None:
        """Initialize the button."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.press_fn(self.device)
