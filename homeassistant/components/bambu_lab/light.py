"""Light platform for the Bambu Lab integration."""

from typing import Any, override

from aiobambulab import BambuLabClient

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BambuLabConfigEntry
from .entity import BambuLabEntity, command

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BambuLabConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light of a Bambu Lab printer."""
    client = entry.runtime_data

    if client.state.chamber_light_on is not None:
        async_add_entities([BambuLabChamberLight(client)])


class BambuLabChamberLight(BambuLabEntity, LightEntity):
    """The light in the chamber of a Bambu Lab printer."""

    _attr_translation_key = "chamber_light"
    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, client: BambuLabClient) -> None:
        """Initialize the light."""
        super().__init__(client)
        self._attr_unique_id = f"{client.serial}_chamber"

    @override
    @property
    def is_on(self) -> bool | None:
        """Return whether the light is on."""
        return self._client.state.chamber_light_on

    @override
    @command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self._client.set_chamber_light(on=True)

    @override
    @command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._client.set_chamber_light(on=False)
