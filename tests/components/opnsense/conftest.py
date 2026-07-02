"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import ARP, CONFIG_DATA, INTERFACES

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
        unique_id="mocked_unique_id",
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
        client = mock_client.return_value
        client.get_host_firmware_version.return_value = "25.7.8"
        client.get_arp_table.return_value = ARP
        client.get_interfaces.return_value = INTERFACES
        client.get_device_unique_id.return_value = "mocked_unique_id"
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.opnsense.async_setup_entry", return_value=True
    ):
        yield
