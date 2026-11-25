"""Support for VeSync buttons."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, override

from pyvesync.base_devices.fryer_base import VeSyncFryer
from pyvesync.base_devices.purifier_base import VeSyncPurifier
from pyvesync.const import AirFryerFeatures, PurifierFeatures
from pyvesync.device_container import DeviceContainer
from pyvesync.utils.errors import VeSyncError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import is_air_fryer, is_purifier
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


@dataclass(frozen=True, kw_only=True)
class VeSyncFryerButtonEntityDescription(ButtonEntityDescription):
    """Describe an air fryer button that acts on one basket."""

    supported_fn: Callable[[VeSyncFryer], bool] = lambda _: True
    press_fn: Callable[[VeSyncFryer, int], Awaitable[bool]]


FRYER_BUTTON_DESCRIPTIONS: Final[tuple[VeSyncFryerButtonEntityDescription, ...]] = (
    VeSyncFryerButtonEntityDescription(
        key="stop_cooking",
        translation_key="stop_cooking",
        press_fn=lambda device, chamber: device.end(chamber),
    ),
    VeSyncFryerButtonEntityDescription(
        key="pause_cooking",
        translation_key="pause_cooking",
        supported_fn=lambda device: AirFryerFeatures.RESUMABLE in device.features,
        press_fn=lambda device, chamber: device.stop(chamber),
    ),
    VeSyncFryerButtonEntityDescription(
        key="resume_cooking",
        translation_key="resume_cooking",
        supported_fn=lambda device: AirFryerFeatures.RESUMABLE in device.features,
        press_fn=lambda device, chamber: device.resume(chamber),
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
        entities: list[ButtonEntity] = []
        for dev in devices:
            if is_purifier(dev):
                entities.extend(
                    VeSyncButtonEntity(dev, description, coordinator)
                    for description in BUTTON_DESCRIPTIONS
                    if description.supported_fn(dev)
                )
            elif is_air_fryer(dev):
                chambers = (1, 2) if dev.is_dual_chamber else (1,)
                entities.extend(
                    VeSyncFryerButtonEntity(dev, description, coordinator, chamber)
                    for description in FRYER_BUTTON_DESCRIPTIONS
                    if description.supported_fn(dev)
                    for chamber in chambers
                )
        async_add_entities(entities)

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
        await _async_press(self.entity_description.press_fn(self.device))
        # The filter life sensor reads the new value from the next poll.
        await self.coordinator.async_request_refresh()


class VeSyncFryerButtonEntity(ButtonEntity, VeSyncBaseEntity[VeSyncFryer]):
    """Air fryer button for one basket."""

    entity_description: VeSyncFryerButtonEntityDescription

    def __init__(
        self,
        device: VeSyncFryer,
        description: VeSyncFryerButtonEntityDescription,
        coordinator: VeSyncDataCoordinator,
        chamber: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(device, coordinator)
        self.entity_description = description
        self._chamber = chamber
        self._attr_unique_id = f"{super().unique_id}-{description.key}"
        if device.is_dual_chamber:
            self._attr_translation_key = f"{description.translation_key}_basket"
            self._attr_translation_placeholders = {"basket": str(chamber)}
        if chamber == 2:
            self._attr_unique_id += "-chamber_2"

    @override
    async def async_press(self) -> None:
        """Press the button."""
        await _async_press(self.entity_description.press_fn(self.device, self._chamber))
        await self.coordinator.async_request_refresh()


async def _async_press(command: Awaitable[bool]) -> None:
    """Send a button command and raise if the device rejects it."""
    try:
        success = await command
    except VeSyncError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_response_error"
        ) from err
    if not success:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_response_error"
        )
