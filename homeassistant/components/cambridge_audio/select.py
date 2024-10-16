"""Support for Cambridge Audio select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import Output

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CambridgeAudioEntity


@dataclass(frozen=True, kw_only=True)
class CambridgeAudioSelectEntityDescription(SelectEntityDescription):
    """Describes Cambridge Audio select entity."""

    value_fn: Callable[[StreamMagicClient], str | None]
    set_value_fn: Callable[[StreamMagicClient, str], Awaitable[None]]


AUDIO_OUTPUT_ENTITY = CambridgeAudioSelectEntityDescription(
    key="audio_output",
    translation_key="audio_output",
    entity_category=EntityCategory.CONFIG,
    value_fn=lambda client: (client.state.audio_output),
    set_value_fn=lambda client, value: print(value),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cambridge Audio select entities based on a config entry."""

    client: StreamMagicClient = entry.runtime_data
    entities = []
    client.audio_output.outputs = [
        Output(id="bt", name="Bluetooth"),
        Output(id="channel_a", name="Speaker A"),
        Output(id="channel_b", name="Speaker B"),
    ]
    if client.audio_output.outputs:
        options = [output.name for output in client.audio_output.outputs]
        entities.append(CambridgeAudioSelect(client, AUDIO_OUTPUT_ENTITY, options))

    async_add_entities(entities)


class CambridgeAudioSelect(CambridgeAudioEntity, SelectEntity):
    """Defines a Cambridge Audio select entity."""

    entity_description: CambridgeAudioSelectEntityDescription

    def __init__(
        self,
        client: StreamMagicClient,
        description: CambridgeAudioSelectEntityDescription,
        options: list[str] | None = None,
    ) -> None:
        """Initialize AirGradient select."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.info.unit_id}-{description.key}"
        self._attr_options = description.options or options

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.client)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.client, option)
