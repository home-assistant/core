"""Support for Imou siren controls."""

from dataclasses import dataclass
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


@dataclass(frozen=True, kw_only=True)
class ImouSirenEntityDescription(SirenEntityDescription):
    """Describes an Imou siren entity."""

    start_param: str = PARAM_SIREN_START
    stop_param: str = PARAM_SIREN_STOP


SIREN_DESCRIPTION = ImouSirenEntityDescription(
    key="siren",
    translation_key="siren",
)


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
            and (
                PARAM_SIREN_START in device.buttons
                or PARAM_SIREN_STOP in device.buttons
            )
        )

    entry.async_on_unload(coordinator.register_new_device_callback(_add_sirens))
    _add_sirens(coordinator.devices)


class ImouSiren(ImouEntity, SirenEntity):
    """Manual siren control for an Imou device.

    The cloud API does not report whether the siren is currently sounding, so
    the entity state stays unknown until a turn on or turn off command succeeds.
    """

    _attr_assumed_state = True
    entity_description: ImouSirenEntityDescription

    def __init__(
        self,
        coordinator: ImouDataUpdateCoordinator,
        device: ImouHaDevice,
    ) -> None:
        """Initialize the siren entity."""
        super().__init__(coordinator, SIREN_DESCRIPTION, device)
        description = self.entity_description
        features = SirenEntityFeature(0)
        if description.start_param in device.buttons:
            features |= SirenEntityFeature.TURN_ON
        if description.stop_param in device.buttons:
            features |= SirenEntityFeature.TURN_OFF
        self._attr_supported_features = features

    def _tracks_local_siren_state(self) -> bool:
        """Return whether turn on/off can both be issued for toggle semantics."""
        features = self.supported_features
        return bool(
            features & SirenEntityFeature.TURN_ON
            and features & SirenEntityFeature.TURN_OFF
        )

    def _set_local_siren_state(self, is_on: bool) -> None:
        """Remember siren on/off after a successful command when toggle is supported."""
        if not self._tracks_local_siren_state():
            return
        self._attr_is_on = is_on
        self.async_write_ha_state()

    @override
    @async_wrap_imou_command("siren_operation_failed")
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Sound the siren."""
        await self.coordinator.device_manager.async_press_button(
            self.device,
            self.entity_description.start_param,
            0,
        )
        self._set_local_siren_state(True)

    @override
    @async_wrap_imou_command("siren_operation_failed")
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Silence the siren."""
        await self.coordinator.device_manager.async_press_button(
            self.device,
            self.entity_description.stop_param,
            0,
        )
        self._set_local_siren_state(False)
