"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

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
def mock_config_entry(
    hass: HomeAssistant, mock_opnsense_client: AsyncMock
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    # Use the mocked client instance instead of creating a real one
    mock_config_entry.runtime_data = {
        CONF_OPNSENSE_CLIENT: mock_opnsense_client.return_value,
        CONF_TRACKER_INTERFACES: [],
    }
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_opnsense_client() -> Generator[AsyncMock]:
    """Override OPNsenseClient in both config_flow and component."""
    with (
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient",
            autospec=True,
        ) as mock_config_flow_client,
        patch(
            "homeassistant.components.opnsense.OPNsenseClient", autospec=True
        ) as mock_component_client,
    ):
        # Set up both clients with the same mock data
        setup_mock_opnsense_client(mock_config_flow_client)
        setup_mock_opnsense_client(mock_component_client)
        yield mock_component_client
