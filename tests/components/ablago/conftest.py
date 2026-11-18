"""Common fixtures for the Ablago tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from ablago import Zaehlerstand
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.ablago.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import setup_integration
from .const import USER_INPUT


@pytest.fixture
def counters_data() -> dict[str, Any]:
    """Return the counters as Ablago sends them."""
    return load_json_object_fixture("zaehler.json", DOMAIN)


@pytest.fixture
def mock_ablago_client(counters_data: dict[str, Any]) -> Generator[MagicMock]:
    """Mock the Ablago client wherever the integration creates one."""
    with patch(
        "homeassistant.components.ablago.coordinator.AblagoClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.zaehler = AsyncMock(return_value=Zaehlerstand.from_api(counters_data))
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ablago.example.org",
        data=USER_INPUT,
        entry_id="01KABLAGOLENA0000000000000",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ablago_client: MagicMock,
) -> MockConfigEntry:
    """Set up the Ablago integration for testing."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
