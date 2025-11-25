"""Fixtures for Essent integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from essent_dynamic_pricing import EssentPrices
import pytest

from homeassistant.components.essent.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Essent",
        data={},
        unique_id=DOMAIN,
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.essent.async_setup_entry",
        return_value=True,
    ) as mock:
        yield mock


@pytest.fixture
def mock_essent_client() -> Generator[AsyncMock]:
    """Mock EssentClient."""
    with (
        patch(
            "homeassistant.components.essent.coordinator.EssentClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.essent.config_flow.EssentClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.async_get_prices.return_value = EssentPrices.from_dict(
            load_json_object_fixture("prices.json", DOMAIN)
        )
        yield client


@pytest.fixture
def platforms() -> list[Platform]:
    """Return platforms to test."""
    return [Platform.SENSOR]


@pytest.fixture
async def setup_sensor_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_essent_client: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up Essent with sensor platform patched in."""
    with patch("homeassistant.components.essent.PLATFORMS", platforms):
        await setup_integration(hass, mock_config_entry)

    return mock_config_entry
