"""Fixtures for OpenRouter integration tests."""

from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.open_router.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.open_router.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="OpenRouter",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "bla",
        },
    )


@dataclass
class Model:
    """Mock model data."""

    id: str
    name: str


@pytest.fixture
async def mock_openai_client() -> AsyncGenerator[AsyncMock]:
    """Initialize integration."""
    with (
        patch(
            "homeassistant.components.open_router.AsyncOpenAI", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.open_router.config_flow.AsyncOpenAI",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.with_options = MagicMock()
        client.with_options.return_value.models = MagicMock()
        client.with_options.return_value.models.list.return_value = (
            get_generator_from_data(
                [
                    Model(id="gpt-4", name="GPT-4"),
                    Model(id="gpt-3.5-turbo", name="GPT-3.5 Turbo"),
                ],
            )
        )
        yield client


@pytest.fixture
async def mock_open_router_client() -> AsyncGenerator[AsyncMock]:
    """Initialize integration."""
    with patch(
        "homeassistant.components.open_router.config_flow.OpenRouterClient",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        yield client


@pytest.fixture(autouse=True)
async def setup_ha(hass: HomeAssistant) -> None:
    """Set up Home Assistant."""
    assert await async_setup_component(hass, "homeassistant", {})


async def get_generator_from_data[DataT](items: list[DataT]) -> AsyncGenerator[DataT]:
    """Return async generator."""
    for item in items:
        yield item
