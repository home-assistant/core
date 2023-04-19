"""Support for Insteon lights via PowerLinc Modem."""
from typing import Any

from pyinsteon.config import ON_LEVEL

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import SIGNAL_ADD_CONFIG_ENTITIES, SIGNAL_ADD_ENTITIES
from .insteon_entity import InsteonConfigEntity, InsteonEntity
from .utils import (
    async_add_insteon_config_entities,
    async_add_insteon_devices,
    async_add_insteon_devices_config,
    async_add_insteon_entities,
)

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

    @callback
    def async_add_insteon_light_config_entities(discovery_info=None):
        """Add the Insteon configuration entities for the platform."""
        async_add_insteon_config_entities(
            hass,
            Platform.LIGHT,
            InsteonDimmerEntity,
            async_add_entities,
            discovery_info,
        )

    signal = f"{SIGNAL_ADD_ENTITIES}_{Platform.LIGHT}"
    async_dispatcher_connect(hass, signal, async_add_insteon_light_entities)
    signal = f"{SIGNAL_ADD_CONFIG_ENTITIES}_{Platform.LIGHT}"
    async_dispatcher_connect(hass, signal, async_add_insteon_light_config_entities)

    async_add_insteon_devices(
        hass, Platform.LIGHT, InsteonDimmerEntity, async_add_entities
    )
    async_add_insteon_devices_config(
        hass, Platform.LIGHT, InsteonDimmerConfigEntity, async_add_entities
    )


class InsteonDimmerEntity(InsteonEntity, LightEntity):
    """A Class for an Insteon light entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._entity.value

    @property
    def is_on(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        elif self._entity.group == 1:
            brightness = self.get_device_property(ON_LEVEL)
        if brightness:
            await self._insteon_device.async_on(
                on_level=brightness, group=self._entity.group
            )
        else:
            await self._insteon_device.async_on(group=self._entity.group)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        await self._insteon_device.async_off(self._entity.group)


class InsteonDimmerConfigEntity(InsteonConfigEntity, LightEntity):
    """A Class for an Insteon light configuration entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self._entity.value

    @property
    def is_on(self) -> bool:
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn light on."""
        brightness = int(kwargs.get(ATTR_BRIGHTNESS, MAX_BRIGHTNESS))
        self._entity.new_value = brightness
        await self._debounce_writer.async_call()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn light off."""
        self._entity.new_value = 0
        await self._debounce_writer.async_call()
