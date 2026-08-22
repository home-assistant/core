"""Button for Midea."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from midealocal.const import DeviceType
from midealocal.device import MideaDevice
from midealocal.devices.e1 import MideaE1Device

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaButtonEntityDescription(ButtonEntityDescription):
    """Description for a Midea button entity."""

    models: list[DeviceType]
    supported_models: list[str]
    press_fn: Callable[[MideaDevice], None]
    available_fn: Callable[[MideaDevice], bool]


def _e1_button_press(device: MideaDevice) -> None:
    """Start the dishwasher using its currently selected work mode."""
    cast(MideaE1Device, device).start_work()


def _e1_button_available(device: MideaDevice) -> bool:
    """Return whether the start button is available for an E1 dishwasher."""
    if not device.get_attribute("power"):
        return False
    mode = device.get_attribute("mode")
    return mode is not None and mode != "none"


BUTTONS: list[MideaButtonEntityDescription] = [
    MideaButtonEntityDescription(
        key="start",
        translation_key="start",
        models=[DeviceType.E1],
        supported_models=["7600024L"],
        press_fn=_e1_button_press,
        available_fn=_e1_button_available,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaButton(device, description)
        for description in BUTTONS
        if device.device_type in description.models
        and device.model in description.supported_models
    )


class MideaButton(MideaEntity, ButtonEntity):
    """Represent a Midea button."""

    entity_description: MideaButtonEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether the device is on and the selected button function is available."""
        return super().available and self.entity_description.available_fn(self._device)

    @override
    def press(self) -> None:
        """Press the button."""
        with midea_api_call():
            self.entity_description.press_fn(self._device)
