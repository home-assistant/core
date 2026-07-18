"""Support for Imou switch controls."""

from typing import Any, override

from pyimouapi.exceptions import ImouException
from pyimouapi.ha_device import ImouHaDevice

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    PARAM_AB_ALARM_SOUND,
    PARAM_AUDIO_ENCODE_CONTROL,
    PARAM_CLOSE_CAMERA,
    PARAM_HEADER_DETECT,
    PARAM_LIGHT,
    PARAM_MOTION_DETECT,
    PARAM_PLUG_SWITCH,
    PARAM_STATE,
    PARAM_WHITE_LIGHT,
    imou_device_identifier,
)
from .coordinator import ImouConfigEntry, ImouDataUpdateCoordinator
from .entity import ImouEntity

PARALLEL_UPDATES = 0

SWITCH_TYPES: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key=PARAM_AB_ALARM_SOUND,
        translation_key=PARAM_AB_ALARM_SOUND,
    ),
    SwitchEntityDescription(
        key=PARAM_AUDIO_ENCODE_CONTROL,
        translation_key=PARAM_AUDIO_ENCODE_CONTROL,
    ),
    SwitchEntityDescription(
        key=PARAM_CLOSE_CAMERA,
        translation_key=PARAM_CLOSE_CAMERA,
    ),
    SwitchEntityDescription(
        key=PARAM_HEADER_DETECT,
        translation_key=PARAM_HEADER_DETECT,
    ),
    SwitchEntityDescription(
        key=PARAM_LIGHT,
        translation_key=PARAM_LIGHT,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key=PARAM_MOTION_DETECT,
        translation_key=PARAM_MOTION_DETECT,
    ),
    SwitchEntityDescription(
        key=PARAM_PLUG_SWITCH,
        translation_key=PARAM_PLUG_SWITCH,
        device_class=SwitchDeviceClass.SWITCH,
    ),
    SwitchEntityDescription(
        key=PARAM_WHITE_LIGHT,
        translation_key=PARAM_WHITE_LIGHT,
    ),
)


def _iter_switches(
    coordinator: ImouDataUpdateCoordinator,
) -> list[tuple[SwitchEntityDescription, ImouHaDevice]]:
    """Return (description, device) pairs for supported switches."""
    return [
        (description, device)
        for device in coordinator.devices
        for description in SWITCH_TYPES
        if description.key in device.switches
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ImouConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Imou switch entities."""
    coordinator = entry.runtime_data

    def _add_switches(new_devices: list[ImouHaDevice]) -> None:
        device_keys = {imou_device_identifier(device) for device in new_devices}
        async_add_entities(
            ImouSwitch(coordinator, description, device)
            for description, device in _iter_switches(coordinator)
            if imou_device_identifier(device) in device_keys
        )

    coordinator.new_device_callbacks.append(_add_switches)

    @callback
    def _remove_new_device_callback() -> None:
        if _add_switches in coordinator.new_device_callbacks:
            coordinator.new_device_callbacks.remove(_add_switches)

    entry.async_on_unload(_remove_new_device_callback)
    _add_switches(coordinator.devices)


class ImouSwitch(ImouEntity, SwitchEntity):
    """Imou switch entity."""

    entity_description: SwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True if the switch is on."""
        return self.device.switches[self._entity_type][PARAM_STATE]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_switch_operation(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_switch_operation(False)

    async def _async_switch_operation(self, enable: bool) -> None:
        """Call the vendor library to change switch state."""
        try:
            await self.coordinator.device_manager.async_switch_operation(
                self.device,
                self._entity_type,
                enable,
            )
        except ImouException as e:
            raise HomeAssistantError(str(e)) from e
        await self.coordinator.async_request_refresh()
