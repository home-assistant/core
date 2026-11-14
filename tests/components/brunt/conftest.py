"""Configuration for brunt tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from brunt import Thing
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.brunt.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.brunt.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-username",
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )


@pytest.fixture
def mock_brunt_client() -> Generator[AsyncMock]:
    """Mock the Brunt client."""
    with patch(
        "homeassistant.components.brunt.coordinator.BruntClientAsync", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.async_get_things.return_value = [
            Thing(
                name="Living room",
                model="Blind Engine",
                fw_version="1.0.0",
                thing_uri="/thing/1",
                serial="1234",
            )
        ]
        yield client
