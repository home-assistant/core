"""Switch for Midea."""

from dataclasses import dataclass
from typing import Any, override

from midealocal.const import DeviceType

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import MideaConfigEntry, MideaEntity, midea_api_call

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class MideaSwitchEntityDescription(SwitchEntityDescription):
    """Description for a Midea switch entity."""

    models: list[DeviceType]


SWITCHES: list[MideaSwitchEntityDescription] = [
    MideaSwitchEntityDescription(
        key="aux_heating",
        translation_key="aux_heating",
        models=[DeviceType.AC, DeviceType.CC, DeviceType.CF],
    ),
    MideaSwitchEntityDescription(
        key="prompt_tone",
        translation_key="prompt_tone",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="screen_display",
        translation_key="screen_display",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="out_silent",
        translation_key="out_silent",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="smart_eye",
        translation_key="smart_eye",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="anion",
        translation_key="anion",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="sound",
        translation_key="sound",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="self_clean",
        translation_key="self_clean",
        models=[DeviceType.AC],
    ),
    MideaSwitchEntityDescription(
        key="disinfect",
        translation_key="disinfect",
        models=[DeviceType.C3],
    ),
    MideaSwitchEntityDescription(
        key="tbh",
        translation_key="tbh",
        models=[DeviceType.C3],
    ),
    MideaSwitchEntityDescription(
        key="zone1_curve",
        translation_key="zone1_curve",
        models=[DeviceType.C3],
    ),
    MideaSwitchEntityDescription(
        key="zone2_curve",
        translation_key="zone2_curve",
        models=[DeviceType.C3],
    ),
    MideaSwitchEntityDescription(
        key="night_light",
        translation_key="night_light",
        models=[DeviceType.CC],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MideaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switches for device."""
    device = config_entry.runtime_data

    async_add_entities(
        MideaSwitch(device, description)
        for description in SWITCHES
        if device.device_type in description.models
        and description.key in device.attributes
    )


class MideaSwitch(MideaEntity, SwitchEntity):
    """Represent a Midea switch."""

    entity_description: MideaSwitchEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        value = self._device.get_attribute(self.entity_description.key)
        if not isinstance(value, bool):
            return None
        return value

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        with midea_api_call():
            self._device.set_attribute(attr=self.entity_description.key, value=True)

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        with midea_api_call():
            self._device.set_attribute(attr=self.entity_description.key, value=False)
