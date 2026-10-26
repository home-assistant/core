"""Support for VeSync buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from pyvesync.base_devices.purifier_base import VeSyncPurifier
from pyvesync.const import PurifierFeatures
from pyvesync.device_container import DeviceContainer
from pyvesync.utils.errors import VeSyncError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_purifier
from .const import DOMAIN, VS_DEVICES, VS_DISCOVERY
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class VeSyncButtonEntityDescription(ButtonEntityDescription):
    """A class that describes custom button entities."""

    supported_fn: Callable[[VeSyncPurifier], bool]
    press_fn: Callable[[VeSyncPurifier], Awaitable[bool]]


BUTTON_DESCRIPTIONS: Final[tuple[VeSyncButtonEntityDescription, ...]] = (
    VeSyncButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
        entity_category=EntityCategory.CONFIG,
        supported_fn=lambda device: PurifierFeatures.RESET_FILTER in device.features,
        press_fn=lambda device: device.reset_filter(),
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
        """Add a button entity for each supported device."""
        async_add_entities(
            VeSyncButtonEntity(dev, description, coordinator)
            for dev in devices
            if is_purifier(dev)
            for description in BUTTON_DESCRIPTIONS
            if description.supported_fn(dev)
        )

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    discover(coordinator.manager.devices)


class VeSyncButtonEntity(ButtonEntity, VeSyncBaseEntity[VeSyncPurifier]):
    """VeSync button entity class."""

    entity_description: VeSyncButtonEntityDescription

    def __init__(
        self,
        device: VeSyncPurifier,
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
        try:
            success = await self.entity_description.press_fn(self.device)
        except VeSyncError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_response_error"
            ) from err
        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_response_error"
            )
        # The filter life sensor reads the new value from the next poll.
        await self.coordinator.async_request_refresh()
