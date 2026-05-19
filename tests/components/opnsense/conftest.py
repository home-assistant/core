"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opnsense import OPNsenseRuntimeData
from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, setup_mock_opnsense_client

from tests.common import MockConfigEntry

CONF_OPNSENSE_CLIENT = "opnsense_client"


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
    mock_config_entry.runtime_data = OPNsenseRuntimeData(
        client=mock_opnsense_client.return_value, tracker_interfaces=[]
    )

    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_opnsense_client() -> Generator[AsyncMock]:
    """Override OPNsenseClient in both config_flow and component."""
    with (
        patch(
            "homeassistant.components.opnsense.config_flow.OPNsenseClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.opnsense.OPNsenseClient",
            new=mock_client,
        ),
    ):
        # Use the same mock for both import locations so test mutations
        # affect the client instance used by config flow and the component.
        setup_mock_opnsense_client(mock_client)
        yield mock_client
