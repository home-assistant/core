"""Platform for light integration."""

from typing import TYPE_CHECKING, Any, override

from boschshcpy import SHCMicromoduleDimmer

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.color import brightness_to_value, value_to_brightness

from . import BoschConfigEntry
from .entity import SHCEntity

PARALLEL_UPDATES = 1

BRIGHTNESS_SCALE = (1, 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SHC light platform."""
    session = config_entry.runtime_data

    shc_info = session.information
    if TYPE_CHECKING:
        assert shc_info is not None and shc_info.unique_id is not None

    async_add_entities(
        SHCDimmerLight(
            hass=hass,
            device=device,
            parent_id=shc_info.unique_id,
            entry_id=config_entry.entry_id,
        )
        for device in session.device_helper.micromodule_dimmers
    )


class SHCDimmerLight(SHCEntity, LightEntity):
    """Representation of a Light Control micromodule dimmer."""

    _attr_name = None
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _device: SHCMicromoduleDimmer

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the dimmer is on."""
        return self._device.binarystate

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness between 1 and 255."""
        return value_to_brightness(BRIGHTNESS_SCALE, self._device.brightness)

    @override
    def turn_on(self, **kwargs: Any) -> None:
        """Turn the dimmer on, optionally setting the brightness."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._device.brightness = round(
                brightness_to_value(BRIGHTNESS_SCALE, brightness)
            )
        if not self.is_on:
            self._device.binarystate = True

    @override
    def turn_off(self, **kwargs: Any) -> None:
        """Turn the dimmer off."""
        self._device.binarystate = False
