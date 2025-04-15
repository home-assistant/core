"""Test mocks and fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sky_remote.const import DEFAULT_PORT, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

SAMPLE_CONFIG = {CONF_HOST: "example.com", CONF_PORT: DEFAULT_PORT}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(domain=DOMAIN, data=SAMPLE_CONFIG)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Stub out setup function."""
    with patch(
        "homeassistant.components.sky_remote.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_remote_control(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Mock skyboxremote library."""
    with (
        patch(
            "homeassistant.components.sky_remote.RemoteControl"
        ) as mock_remote_control,
        patch(
            "homeassistant.components.sky_remote.config_flow.RemoteControl",
            mock_remote_control,
        ),
    ):
        mock_remote_control._instance_mock = MagicMock(host="example.com")
        mock_remote_control._instance_mock.check_connectable = AsyncMock(True)
        mock_remote_control.return_value = mock_remote_control._instance_mock
        yield mock_remote_control
