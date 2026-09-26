"""OpenGarage opener light."""

from typing import Any, cast, override

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import OpenGarageConfigEntry
from .entity import OpenGarageCapabilityEntity, async_add_capability_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenGarageConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the opener light when supported."""
    async_add_capability_entities(
        entry.runtime_data,
        async_add_entities,
        {
            "light_control": lambda: OpenGarageLight(
                entry.runtime_data,
                cast(str, entry.unique_id),
                EntityDescription(key="light", translation_key="light"),
            )
        },
    )


class OpenGarageLight(OpenGarageCapabilityEntity, LightEntity):
    """Representation of the opener's light."""

    capability = "light_control"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    @callback
    @override
    def _update_attr(self) -> None:
        """Update the reported light state."""
        self._attr_is_on = self.coordinator.data.light_on

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        await self._async_set_light(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._async_set_light(False)

    async def _async_set_light(self, on: bool) -> None:
        """Let the library serialize and conditionally toggle the light."""
        await self.coordinator.async_command(
            lambda: self.coordinator.open_garage_connection.set_light(on),
            allow_noop=True,
        )
        await self.coordinator.async_request_refresh()
