"""Support for Imou siren controls."""

from typing import Any, override

from pyimouapi.const import PARAM_SIREN_START, PARAM_SIREN_STOP
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityDescription,
    SirenEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import imou_device_identifier
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity
from .helpers import async_wrap_imou_command

PARALLEL_UPDATES = 0

SIREN_DESCRIPTION = SirenEntityDescription(
    key="siren",
    translation_key="siren",
)


def _device_has_siren(device: ImouHaDevice) -> bool:
    """Return whether the device can start or stop the siren."""
    return PARAM_SIREN_START in device.buttons or PARAM_SIREN_STOP in device.buttons


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou siren entities."""
    coordinator = entry.runtime_data

    def _add_sirens(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSiren(coordinator, device)
            for device in coordinator.devices
            if imou_device_identifier(device) in device_keys
            and _device_has_siren(device)
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_sirens))
    _add_sirens(coordinator.devices)


class ImouSiren(ImouEntity, SirenEntity):
    """Manual siren control for an Imou device.

    The cloud API does not report whether the siren is currently sounding, so
    the entity state stays unknown. Turn on and turn off still send the start
    and stop commands.
    """

    entity_description = SIREN_DESCRIPTION
    _attr_supported_features = SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the siren entity."""
        super().__init__(coordinator, SIREN_DESCRIPTION, device)

    @override
    @async_wrap_imou_command("siren_operation_failed")
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Sound the siren."""
        await self.coordinator.device_manager.async_press_button(
            self.device,
            PARAM_SIREN_START,
            0,
        )

    @override
    @async_wrap_imou_command("siren_operation_failed")
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Silence the siren."""
        await self.coordinator.device_manager.async_press_button(
            self.device,
            PARAM_SIREN_STOP,
            0,
        )
