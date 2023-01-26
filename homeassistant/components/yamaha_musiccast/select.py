"""The select entities for musiccast."""
from __future__ import annotations

from aiomusiccast.capabilities import OptionSetter

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, MusicCastCapabilityEntity, MusicCastDataUpdateCoordinator
from .const import TRANSLATION_KEY_MAPPING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast select entities based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    select_entities = []

    for capability in coordinator.data.capabilities:
        if isinstance(capability, OptionSetter):
            select_entities.append(SelectableCapapility(coordinator, capability))

    for zone, data in coordinator.data.zones.items():
        for capability in data.capabilities:
            if isinstance(capability, OptionSetter):
                select_entities.append(
                    SelectableCapapility(coordinator, capability, zone)
                )

    async_add_entities(select_entities)


class SelectableCapapility(MusicCastCapabilityEntity, SelectEntity):
    """Representation of a MusicCast Select entity."""

    capability: OptionSetter

    async def async_select_option(self, option: str) -> None:
        """Select the given option."""
        # the zone_sleep capability is a dict[int, str].  The dictionary value
        # has spaces in it.  Translations require sluggified options, i.e. no spaces or integers
        # To ensure that, return a dictionary that maps the stringified key to the key.
        # All other capabilities do not have this issue.
        values = (
            {str(key): key for key in self.capability.options.keys()}
            if self.translation_key == "zone_sleep"
            else {val: key for key, val in self.capability.options.items()}
        )
        value = values[option]
        await self.capability.set(value)

    @property
    def translation_key(self) -> str | None:
        """Return the translation key to translate the entity's states."""
        return TRANSLATION_KEY_MAPPING.get(self.capability.id)

    @property
    def options(self) -> list[str]:
        """Return the list possible options."""
        # the zone_sleep capability is a dict[int, str].  The dictionary value
        # has spaces in it.  Translations require sluggified options, i.e. no spaces or integers
        # To ensure that, return a list of strings.  This will allow us to map the
        # stringified key to the capability option.
        # All other capabilities do not have this issue.
        options = (
            self.capability.options.keys()
            if self.translation_key == "zone_sleep"
            else self.capability.options.values()
        )
        return [str(x) for x in options]

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        if (value := self.capability.current) is None:
            return None
        return str(value)
