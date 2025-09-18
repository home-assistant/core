"""Support for Cambridge Audio select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from aiostreammagic import StreamMagicClient
from aiostreammagic.models import ControlBusMode, DisplayBrightness

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import CambridgeAudioConfigEntry
from .entity import CambridgeAudioEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class CambridgeAudioSelectEntityDescription(SelectEntityDescription):
    """Describes Cambridge Audio select entity."""

    options_fn: Callable[[StreamMagicClient], list[str]] = field(default=lambda _: [])
    load_fn: Callable[[StreamMagicClient], bool] = field(default=lambda _: True)
    value_fn: Callable[[StreamMagicClient], str | None]
    set_value_fn: Callable[[StreamMagicClient, str], Awaitable[None]]


async def _audio_output_set_value_fn(client: StreamMagicClient, value: str) -> None:
    """Set the audio output using the display name."""
    audio_output_id = next(
        (output.id for output in client.audio_output.outputs if value == output.name),
        None,
    )
    assert audio_output_id is not None
    await client.set_audio_output(audio_output_id)


def _audio_output_value_fn(client: StreamMagicClient) -> str | None:
    """Convert the current audio output id to name."""
    return next(
        (
            output.name
            for output in client.audio_output.outputs
            if client.state.audio_output == output.id
        ),
        None,
    )


CONTROL_ENTITIES: tuple[CambridgeAudioSelectEntityDescription, ...] = (
    CambridgeAudioSelectEntityDescription(
        key="display_brightness",
        translation_key="display_brightness",
        options=[
            DisplayBrightness.BRIGHT.value,
            DisplayBrightness.DIM.value,
            DisplayBrightness.OFF.value,
        ],
        entity_category=EntityCategory.CONFIG,
        load_fn=lambda client: client.display.brightness != DisplayBrightness.NONE,
        value_fn=lambda client: client.display.brightness,
        set_value_fn=lambda client, value: client.set_display_brightness(
            DisplayBrightness(value)
        ),
    ),
    CambridgeAudioSelectEntityDescription(
        key="audio_output",
        translation_key="audio_output",
        entity_category=EntityCategory.CONFIG,
        options_fn=lambda client: [
            output.name for output in client.audio_output.outputs
        ],
        load_fn=lambda client: len(client.audio_output.outputs) > 0,
        value_fn=_audio_output_value_fn,
        set_value_fn=_audio_output_set_value_fn,
    ),
    CambridgeAudioSelectEntityDescription(
        key="control_bus_mode",
        translation_key="control_bus_mode",
        options=[
            ControlBusMode.AMPLIFIER.value,
            ControlBusMode.RECEIVER.value,
            ControlBusMode.OFF.value,
        ],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda client: client.state.control_bus,
        set_value_fn=lambda client, value: client.set_control_bus_mode(
            ControlBusMode(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CambridgeAudioConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cambridge Audio select entities based on a config entry."""

    client: StreamMagicClient = entry.runtime_data
    entities: list[CambridgeAudioSelect] = [
        CambridgeAudioSelect(client, description)
        for description in CONTROL_ENTITIES
        if description.load_fn(client)
    ]
    async_add_entities(entities)


class CambridgeAudioSelect(CambridgeAudioEntity, SelectEntity):
    """Defines a Cambridge Audio select entity."""

    entity_description: CambridgeAudioSelectEntityDescription

    def __init__(
        self,
        client: StreamMagicClient,
        description: CambridgeAudioSelectEntityDescription,
    ) -> None:
        """Initialize Cambridge Audio select."""
        super().__init__(client)
        self.entity_description = description
        self._attr_unique_id = f"{client.info.unit_id}-{description.key}"
        options_fn = description.options_fn(client)
        if options_fn:
            self._attr_options = options_fn

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self.client)

    @command
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self.client, option)
