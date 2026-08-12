"""Button for Midea."""

from dataclasses import dataclass
from typing import override

from midealocal.const import DeviceType
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
    device_models: list[str]


BUTTONS: list[MideaButtonEntityDescription] = [
    MideaButtonEntityDescription(
        key="start",
        translation_key="start",
        models=[DeviceType.E1],
        device_models=["7600024L"],
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
        and device.model in description.device_models
    )


class MideaButton(MideaEntity, ButtonEntity):
    """Represent a Midea button."""

    _device: MideaE1Device
    entity_description: MideaButtonEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return whether the device is on and has a work mode selected.

        Mode code 0 ("Neutral Gear") means no wash program is selected, so
        pressing start would have nothing to run.
        """
        if not super().available or not self._device.get_attribute("power"):
            return False
        mode_name = self._device.get_attribute("mode")
        return mode_name is not None and mode_name != self._device.modes.get(0)

    @override
    def press(self) -> None:
        """Start the dishwasher using its currently selected work mode."""
        with midea_api_call():
            self._device.start_work()
