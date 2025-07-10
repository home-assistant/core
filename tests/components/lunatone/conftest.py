"""Fixtures for Lunatone tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.const import CONF_URL

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.lunatone.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_lunatone_auth() -> Generator[AsyncMock]:
    """Mock a Lunatone auth object."""
    with (
        patch(
            "homeassistant.components.lunatone.Auth",
            autospec=True,
        ) as mock_auth,
        patch(
            "homeassistant.components.lunatone.config_flow.Auth",
            new=mock_auth,
        ),
    ):
        auth = mock_auth.return_value
        auth.base_url = "http://10.0.0.131"
        yield auth


@pytest.fixture
def mock_lunatone_info() -> Generator[AsyncMock]:
    """Mock a Lunatone info object."""
    with (
        patch(
            "homeassistant.components.lunatone.Info",
            autospec=True,
        ) as mock_info,
        patch(
            "homeassistant.components.lunatone.config_flow.Info",
            new=mock_info,
        ),
    ):
        info = mock_info.return_value
        info.name = "Test"
        info.version = "1.14.1"
        info.serial_number = "12345"
        yield info


@pytest.fixture
def mock_lunatone_scan() -> Generator[AsyncMock]:
    """Mock a Lunatone scan object."""
    with patch(
        "homeassistant.components.lunatone.config_flow.DALIScan", autospec=True
    ) as mock_scan:
        scan = mock_scan.return_value
        scan.is_busy = False
        yield scan


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_URL: "http://10.0.0.131"},
        unique_id="12345",
    )
