"""Number platform support for WeMo."""
from __future__ import annotations

import asyncio
import math

from pywemo import Dimmer

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN as WEMO_DOMAIN
from .entity import WemoEntity
from .wemo_device import DeviceCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entry."""

    async def _discovered_wemo(coordinator: DeviceCoordinator) -> None:
        """Handle a discovered Wemo device."""
        async_add_entities([DimmerBrightness(coordinator)])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, f"{WEMO_DOMAIN}.number", _discovered_wemo)
    )

    await asyncio.gather(
        *(
            _discovered_wemo(coordinator)
            for coordinator in hass.data[WEMO_DOMAIN]["pending"].pop("number")
        )
    )


class DimmerBrightness(WemoEntity, NumberEntity):
    """WeMo Dimmer brightness entity.

    WeMo allows controlling the brightness even when the device is off. Home
    Assistant provides no other way to adjust the brightness level when the
    light is off, so we add this separate Number entity to control the
    brightness independent of the on/off binary state.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_max_value = 255
    _attr_native_min_value = 1
    _attr_number_mode = NumberMode.SLIDER
    _name_suffix = "Brightness"
    wemo: Dimmer

    @property
    def native_value(self) -> float | None:
        """Return the brightness of this light."""
        wemo_brightness: int = self.wemo.get_brightness()
        return float(round((wemo_brightness * 255) / 100))

    def set_native_value(self, value: float) -> None:
        """Set the brightness of the light."""
        with self._wemo_call_wrapper("set brightness"):
            brightness = math.ceil((value / 255) * 100)
            self.wemo.basicevent.SetBinaryState(brightness=brightness)
