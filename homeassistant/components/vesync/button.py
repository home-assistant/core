"""Support for VeSync buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from pyvesync.base_devices import VeSyncBaseDevice
from pyvesync.const import PurifierFeatures
from pyvesync.device_container import DeviceContainer

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_purifier
from .const import VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

PARALLEL_UPDATES = 1


def _reset_filter(device: VeSyncBaseDevice) -> Awaitable[bool]:
    """Reset the filter life of a purifier."""
    if is_purifier(device):
        return device.reset_filter()
    raise HomeAssistantError("Device does not support resetting the filter.")


@dataclass(frozen=True, kw_only=True)
class VeSyncButtonEntityDescription(ButtonEntityDescription):
    """A class that describes custom button entities."""

    exists_fn: Callable[[VeSyncBaseDevice], bool]
    press_fn: Callable[[VeSyncBaseDevice], Awaitable[bool]]


BUTTON_DESCRIPTIONS: Final[tuple[VeSyncButtonEntityDescription, ...]] = (
    VeSyncButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
        entity_category=EntityCategory.CONFIG,
        exists_fn=(
            lambda device: (
                is_purifier(device) and PurifierFeatures.RESET_FILTER in device.features
            )
        ),
        press_fn=_reset_filter,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VesyncConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button platform."""

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
    """Add a button entity for each supported device."""
    async_add_entities(
        VeSyncButtonEntity(dev, description, coordinator)
        for dev in devices
        for description in BUTTON_DESCRIPTIONS
        if description.exists_fn(dev)
    )


class VeSyncButtonEntity(ButtonEntity, VeSyncBaseEntity[VeSyncBaseDevice]):
    """VeSync button entity class."""

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

    @override
    async def async_press(self) -> None:
        """Press the button."""
        if not await self.entity_description.press_fn(self.device):
            if self.device.last_response:
                raise HomeAssistantError(self.device.last_response.message)
            raise HomeAssistantError("Unknown error pressing button, no response.")

        # The filter life sensor reads the new value from the next poll.
        await self.coordinator.async_request_refresh()
