"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from aiopnsense import OPNsenseClient
import pytest

from homeassistant.components.opnsense.const import (
    CONF_OPNSENSE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, setup_mock_opnsense_client

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    opnsense_client = OPNsenseClient(
        "http://router.lan/api",
        "key",
        "secret",
        None,
        opts={"verify_ssl": False},
    )
    mock_config_entry.runtime_data = {
        CONF_OPNSENSE_CLIENT: opnsense_client,
        CONF_TRACKER_INTERFACES: [],
    }
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_opnsense_client() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.config_flow.OPNsenseClient", autospec=True
    ) as mock_opnsense_client:
        setup_mock_opnsense_client(mock_opnsense_client)
        yield mock_opnsense_client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
