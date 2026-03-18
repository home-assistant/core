"""Configuration for Velux tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.velux import DOMAIN
from homeassistant.components.velux.binary_sensor import Window
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD

from tests.common import MockConfigEntry


# Fixtures for the config flow tests
@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.velux.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_velux_client() -> Generator[AsyncMock]:
    """Mock a Velux client."""
    with (
        patch(
            "homeassistant.components.velux.config_flow.PyVLX",
            autospec=True,
        ) as mock_client,
    ):
        client = mock_client.return_value
        yield client


@pytest.fixture
def mock_user_config_entry() -> MockConfigEntry:
    """Return the user config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
        },
    )


@pytest.fixture
def mock_discovered_config_entry() -> MockConfigEntry:
    """Return the user config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="127.0.0.1",
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PASSWORD: "NotAStrongPassword",
            CONF_MAC: "64:61:84:00:ab:cd",
        },
        unique_id="VELUX_KLF_ABCD",
    )


# fixtures for the binary sensor tests
@pytest.fixture
def mock_window() -> AsyncMock:
    """Create a mock Velux window with a rain sensor."""
    window = AsyncMock(spec=Window, autospec=True)
    window.name = "Test Window"
    window.rain_sensor = True
    window.serial_number = "123456789"
    window.get_limitation.return_value = MagicMock(min_value=0)
    window.is_opening = False
    window.is_closing = False
    window.position = MagicMock(position_percent=30, closed=False)
    return window


@pytest.fixture
def mock_pyvlx(mock_window: MagicMock) -> MagicMock:
    """Create the library mock."""
    pyvlx = MagicMock()
    pyvlx.nodes = [mock_window]
    pyvlx.load_scenes = AsyncMock()
    pyvlx.load_nodes = AsyncMock()
    pyvlx.disconnect = AsyncMock()
    return pyvlx


@pytest.fixture
def mock_module(mock_pyvlx: MagicMock) -> Generator[AsyncMock]:
    """Create the Velux module mock."""
    with (
        patch(
            "homeassistant.components.velux.VeluxModule",
            autospec=True,
        ) as mock_velux,
    ):
        module = mock_velux.return_value
        module.pyvlx = mock_pyvlx
        yield module


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "testhost",
            CONF_PASSWORD: "testpw",
        },
    )
