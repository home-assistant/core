"""Support for buttons."""

from dataclasses import dataclass
from typing import Final, override

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator, alexa_api_call
from .entity import AmazonEntity, AmazonServiceEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AmazonButtonEntityDescription(ButtonEntityDescription):
    """Amazon Devices button entity description."""

    capability: str


DEVICE_BUTTONS: Final = {
    AmazonButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        capability="ALEXA_DEVICE_REBOOT",
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for Alexa Devices."""
    coordinator = entry.runtime_data

    known_routines: set[str] = set()
    known_devices: set[str] = set()

    def _check_routines_devices() -> None:
        current_routines = set(coordinator.api.routines)
        new_routines = current_routines - known_routines
        if new_routines:
            known_routines.update(new_routines)
            async_add_entities(
                AmazonRoutineButton(coordinator, routine) for routine in new_routines
            )

        current_devices = set(coordinator.data)
        new_devices = current_devices - known_devices
        if new_devices:
            known_devices.update(new_devices)
            async_add_entities(
                AmazonDeviceButton(coordinator, serial_num, button_desc)
                for button_desc in DEVICE_BUTTONS
                for serial_num in new_devices
                if button_desc.capability in coordinator.data[serial_num].capabilities
            )

    _check_routines_devices()
    entry.async_on_unload(coordinator.async_add_listener(_check_routines_devices))


class AmazonRoutineButton(AmazonServiceEntity, ButtonEntity):
    """Button entity for Alexa routine."""

    def __init__(self, coordinator: AmazonDevicesCoordinator, routine: str) -> None:
        """Initialize the routine button entity."""
        self._routine = routine
        super().__init__(
            coordinator,
            EntityDescription(key=slugify(routine), name=routine),
        )

    @override
    async def async_press(self) -> None:
        """Handle button press action."""
        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.call_routine(self._routine)


class AmazonDeviceButton(AmazonEntity, ButtonEntity):
    """Button entity for Alexa device."""

    @override
    async def async_press(self) -> None:
        """Handle button press action."""
        async with alexa_api_call(self.coordinator):
            await self.coordinator.api.restart_device(self.device)
