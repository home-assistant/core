"""niko_home_control integration tests configuration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.niko_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_niko_home_control_connection() -> Generator[AsyncMock]:
    """Mock a NHC client."""
    with (
        patch(
            "homeassistant.components.niko_home_control.config_flow.NikoHomeControlConnection",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        client.return_value = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN, title="Niko Home Control", data={CONF_HOST: "192.168.0.123"}
    )
