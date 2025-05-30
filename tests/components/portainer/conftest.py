"""Common fixtures for the Portainer tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiotainer.model import NodeData
from aiotainer.utils import portainer_list_to_dictionary
import pytest

from homeassistant.components.portainer.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_URL, CONF_VERIFY_SSL

from tests.common import MockConfigEntry, load_json_value_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.portainer.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="values")
def mock_values() -> dict[str, NodeData]:
    """Fixture to set correct scope for the token."""
    return portainer_list_to_dictionary(
        load_json_value_fixture("portainer.json", DOMAIN)
    )


@pytest.fixture
def mock_portainer_client(values) -> Generator[MagicMock]:
    """Mock APSystems lib."""
    with (
        patch(
            "homeassistant.components.portainer.PortainerClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.portainer.config_flow.PortainerClient",
            new=mock_client,
        ),
    ):
        mock_api = mock_client.return_value
        mock_api.get_status.return_value = values
        yield mock_api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ACCESS_TOKEN: "prt_xxx",
            CONF_URL: "https://127.0.0.1:9443",
            CONF_VERIFY_SSL: True,
        },
        unique_id="MY_SERIAL_NUMBER",
    )
