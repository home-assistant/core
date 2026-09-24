"""Select for Midea."""

from dataclasses import dataclass
from typing import override

from midealocal.const import DeviceType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaSelectEntityDescription(SelectEntityDescription):
    """Description for a Midea select entity."""

    models: list[DeviceType]
    options_attribute: str
    """Device property name returning the list of valid option strings."""
    requires_power: bool = False
    """Entity is only operable while the device's ``power`` attribute is on."""


SELECTS: list[MideaSelectEntityDescription] = [
    MideaSelectEntityDescription(
        key="direction",
        translation_key="direction",
        models=[DeviceType.X40],
        options_attribute="directions",
    ),
    MideaSelectEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        models=[DeviceType.A1, DeviceType.FC, DeviceType.FD],
        options_attribute="fan_speeds",
    ),
    MideaSelectEntityDescription(
        key="water_level_set",
        translation_key="water_level_set",
        models=[DeviceType.A1],
        options_attribute="water_level_sets",
    ),
    MideaSelectEntityDescription(
        key="wind_lr_angle",
        translation_key="wind_lr_angle",
        models=[DeviceType.AC],
        options_attribute="wind_lr_angles",
        requires_power=True,
    ),
    MideaSelectEntityDescription(
        key="wind_ud_angle",
        translation_key="wind_ud_angle",
        models=[DeviceType.AC],
        options_attribute="wind_ud_angles",
        requires_power=True,
    ),
    MideaSelectEntityDescription(
        key="rate_select",
        translation_key="rate_select",
        models=[DeviceType.AC],
        options_attribute="rate_selects",
        requires_power=True,
    ),
    MideaSelectEntityDescription(
        key="silent_level",
        translation_key="silent_level",
        models=[DeviceType.C3],
        options_attribute="silent_modes",
    ),
    MideaSelectEntityDescription(
        key="oscillation_mode",
        translation_key="oscillation_mode",
        models=[DeviceType.FA],
        options_attribute="oscillation_modes",
    ),
    MideaSelectEntityDescription(
        key="oscillation_angle",
        translation_key="oscillation_angle",
        models=[DeviceType.FA],
        options_attribute="oscillation_angles",
    ),
    MideaSelectEntityDescription(
        key="tilting_angle",
        translation_key="tilting_angle",
        models=[DeviceType.FA],
        options_attribute="tilting_angles",
    ),
    MideaSelectEntityDescription(
        key="detect_mode",
        translation_key="detect_mode",
        models=[DeviceType.FC],
        options_attribute="detect_modes",
    ),
    MideaSelectEntityDescription(
        key="mode",
        translation_key="mode",
        models=[DeviceType.FC],
        options_attribute="modes",
    ),
    MideaSelectEntityDescription(
        key="screen_display",
        translation_key="screen_display",
        models=[DeviceType.FC, DeviceType.FD],
        options_attribute="screen_displays",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaSelect(device, description)
        for description in SELECTS
        if device.device_type in description.models
        and description.key in device.attributes
    )


class MideaSelect(MideaEntity, SelectEntity):
    """Represent a Midea select."""

    entity_description: MideaSelectEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return entity availability."""
        if not super().available:
            return False
        if self.entity_description.requires_power:
            return bool(self._device.get_attribute("power"))
        return True

    @property
    @override
    def options(self) -> list[str]:
        """Return the list of valid options."""
        return getattr(self._device, self.entity_description.options_attribute)

    @property
    @override
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        value = self._device.get_attribute(self.entity_description.key)
        if not isinstance(value, str):
            return None
        return value

    @override
    def select_option(self, option: str) -> None:
        """Select an option."""
        with midea_api_call():
            self._device.set_attribute(attr=self.entity_description.key, value=option)
