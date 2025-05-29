"""Support for the Switchbot Light."""

from homeassistant.components.light import ColorMode, LightEntity, LightEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudLight(data.api, device, coordinator)
        for device, coordinator in data.devices.lights
    )


class SwitchBotCloudLight(SwitchBotCloudEntity, LightEntity):
    """Representation of a SwitchBot Battery Circulator Fan."""

    _attr_supported_features = (
        LightEntityFeature.FLASH
        | LightEntityFeature.EFFECT
        | LightEntityFeature.TRANSITION
    )

    _attr_supported_color_modes = {
        ColorMode.ONOFF,
        ColorMode.BRIGHTNESS,
        ColorMode.COLOR_TEMP,
        ColorMode.RGB,
    }

    _attr_max_color_temp_kelvin = 100
    _attr_min_color_temp_kelvin = 1
