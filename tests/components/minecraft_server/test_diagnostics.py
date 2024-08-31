"""Tests for Minecraft Server diagnostics."""
from unittest.mock import patch

from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .const import (
    TEST_BEDROCK_STATUS_RESPONSE,
    TEST_HOST,
    TEST_JAVA_STATUS_RESPONSE,
    TEST_PORT,
)

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("mock_config_entry", "server", "status_response"),
    [
        ("java_mock_config_entry", JavaServer, TEST_JAVA_STATUS_RESPONSE),
        ("bedrock_mock_config_entry", BedrockServer, TEST_BEDROCK_STATUS_RESPONSE),
    ],
)
async def test_config_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    server: JavaServer | BedrockServer,
    status_response: JavaStatusResponse | BedrockStatusResponse,
    request: pytest.FixtureRequest,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fetching of the config entry diagnostics."""

    # Use 'request' fixture to access 'mock_config_entry' fixture, as it cannot be used directly in 'parametrize'.
    mock_config_entry = request.getfixturevalue(mock_config_entry)
    mock_config_entry.add_to_hass(hass)

    if server.__name__ == "JavaServer":
        lookup_function_name = "async_lookup"
    else:
        lookup_function_name = "lookup"

    # Setup mock entry.
    with patch(
        f"mcstatus.server.{server.__name__}.{lookup_function_name}",
        return_value=server(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        f"mcstatus.server.{server.__name__}.async_status",
        return_value=status_response,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Test diagnostics.
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
