"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyopnsense import diagnostics
import pytest

from homeassistant.components.opnsense.const import (
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, setup_mock_diagnostics

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    interfaces_client = diagnostics.InterfaceClient(
        api_key="key",
        api_secret="secret",
        base_url="http://router.lan/api",
        verify_cert=False,
    )
    mock_config_entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: [],
    }
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_diagnostics() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)
        yield mock_diagnostics


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
