"""Tests for the Twitch component."""

from collections.abc import AsyncGenerator, AsyncIterator
from typing import Any, Generic, TypeVar

from twitchAPI.object.base import TwitchObject

from homeassistant.components.twitch.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from tests.common import MockConfigEntry, async_load_json_array_fixture


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


TwitchType = TypeVar("TwitchType", bound=TwitchObject)


class TwitchIterObject(Generic[TwitchType]):
    """Twitch object iterator."""

    raw_data: JsonArrayType
    data: list
    total: int

    def __init__(
        self, hass: HomeAssistant, fixture: str, target_type: type[TwitchType]
    ) -> None:
        """Initialize object."""
        self.hass = hass
        self.fixture = fixture
        self.target_type = target_type

    async def __aiter__(self) -> AsyncIterator[TwitchType]:
        """Return async iterator."""
        if not hasattr(self, "raw_data"):
            self.raw_data = await async_load_json_array_fixture(
                self.hass, self.fixture, DOMAIN
            )
            self.data = [self.target_type(**item) for item in self.raw_data]
            self.total = len(self.raw_data)
        async for item in get_generator_from_data(self.raw_data, self.target_type):
            yield item


async def get_generator(
    hass: HomeAssistant, fixture: str, target_type: type[TwitchType]
) -> AsyncGenerator[TwitchType]:
    """Return async generator."""
    data = await async_load_json_array_fixture(hass, fixture, DOMAIN)
    async for item in get_generator_from_data(data, target_type):
        yield item


async def get_generator_from_data(
    items: list[dict[str, Any]], target_type: type[TwitchType]
) -> AsyncGenerator[TwitchType]:
    """Return async generator."""
    for item in items:
        yield target_type(**item)
