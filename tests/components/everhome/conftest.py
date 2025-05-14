"""Common fixtures for the everHome tests."""

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from ecotracker.data import EcoTrackerData
import pytest

from homeassistant.components.everhome.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.everhome.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_everhome_client() -> Generator[AsyncMock]:
    """Mock a new everHome client."""
    with (
        patch(
            "homeassistant.components.everhome.EcoTracker",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.everhome.config_flow.EcoTracker",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.ip_address = "192.168.178.104"
        client.async_update.return_value = True
        client.get_all_data.return_value = json.loads(load_fixture("data.json", DOMAIN))
        client.get_data.return_value = EcoTrackerData.from_json(
            load_fixture("data.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a everHome config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="everHome-abcdef123456",
        data={CONF_HOST: "192.168.178.104"},
        unique_id="abcdef123456",
        entry_id="89TR7C1642389NZZXYBBQDJMT3",
    )
