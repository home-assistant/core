"""Common fixtures for the Knocki tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from knocki import TokenResponse, Trigger
import pytest

from homeassistant.components.knocki.const import DOMAIN
from homeassistant.const import CONF_TOKEN

from tests.common import MockConfigEntry, load_json_array_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.knocki.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_knocki_client() -> Generator[AsyncMock]:
    """Mock a Knocki client."""
    with (
        patch(
            "homeassistant.components.knocki.KnockiClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.knocki.config_flow.KnockiClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.login.return_value = TokenResponse(token="test-token", user_id="test-id")
        client.get_triggers.return_value = [
            Trigger.from_dict(trigger)
            for trigger in load_json_array_fixture("triggers.json", DOMAIN)
        ]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Knocki",
        unique_id="test-id",
        data={
            CONF_TOKEN: "test-token",
        },
    )
