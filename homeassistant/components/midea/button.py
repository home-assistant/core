"""Button for Midea."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from midealocal.const import DeviceType
from midealocal.device import MideaDevice
from midealocal.devices.ac import MideaACDevice
from midealocal.devices.e1 import MideaE1Device

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaButtonEntityDescription(ButtonEntityDescription):
    """Description for a Midea button entity."""

    models: list[DeviceType]
    press_fn: Callable[[MideaDevice], None]
    supported_models: list[str] | None = None
    supported_property_name: str | None = None


def _ac_reset_filter_press(device: MideaDevice) -> None:
    """Reset filter counters."""
    cast(MideaACDevice, device).reset_filter()


def _e1_button_press(device: MideaDevice) -> None:
    """Start the dishwasher using its currently selected work mode."""
    if not device.get_attribute("power"):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="e1_device_off",
        )
    cast(MideaE1Device, device).start_work()


BUTTONS: list[MideaButtonEntityDescription] = [
    MideaButtonEntityDescription(
        key="start",
        translation_key="start",
        models=[DeviceType.E1],
        supported_models=["7600024L"],
        press_fn=_e1_button_press,
    ),
    MideaButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
        entity_category=EntityCategory.CONFIG,
        models=[DeviceType.AC],
        supported_property_name="is_filter_reset_supported",
        press_fn=_ac_reset_filter_press,
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
        and (
            description.supported_models is None
            or device.model in description.supported_models
        )
        and (
            description.supported_property_name is None
            or getattr(device, description.supported_property_name, False)
        )
    )


class MideaButton(MideaEntity, ButtonEntity):
    """Represent a Midea button."""

    entity_description: MideaButtonEntityDescription

    @override
    async def async_press(self) -> None:
        """Press the button."""
        with midea_api_call():
            await self.hass.async_add_executor_job(
                self.entity_description.press_fn, self._device
            )
