"""Smarty tests configuration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry
from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override integration setup."""
    with patch(
        "homeassistant.components.niko_home_control.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nhc() -> Generator[AsyncMock]:
    """Mock a Smarty client."""
    with (
        patch(
            "homeassistant.components.niko_home_control.NikoHomeControlConnection",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.niko_home_control.config_flow.NikoHomeControlConnection",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.return_value = True
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "0.0.0.0"})
