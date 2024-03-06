"""Support for Insteon lights via PowerLinc Modem."""
from typing import Any

from pyinsteon.config import ON_LEVEL
from pyinsteon.device_types.device_base import Device as InsteonDevice

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonEntity
from .utils import async_add_insteon_devices, async_add_insteon_entities

MAX_BRIGHTNESS = 255


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Insteon lights from a config entry."""

    @callback
    def async_add_insteon_light_entities(discovery_info=None):
        """Add the Insteon entities for the platform."""
        async_add_insteon_entities(
            hass,
            Platform.LIGHT,
            InsteonDimmerEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.LIGHT}"
    async_dispatcher_connect(hass, signal, async_add_insteon_light_entities)
    async_add_insteon_devices(
        hass,
        Platform.LIGHT,
        InsteonDimmerEntity,
        async_add_entities,
    )


class InsteonDimmerEntity(InsteonEntity, LightEntity):
    """A Class for an Insteon light entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, device: InsteonDevice, group: int) -> None:
        """Init the InsteonDimmerEntity entity."""
        super().__init__(device=device, group=group)
        if not self._insteon_device_group.is_dimmable:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._insteon_device_group.value

    @property
    def is_on(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        elif self._insteon_device_group.group == 1:
            brightness = self.get_device_property(ON_LEVEL)
        if brightness:
            await self._insteon_device.async_on(
                on_level=brightness, group=self._insteon_device_group.group
            )
        else:
            await self._insteon_device.async_on(group=self._insteon_device_group.group)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self._insteon_device.async_off(self._insteon_device_group.group)
