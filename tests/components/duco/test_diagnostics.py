"""Tests for the Duco diagnostics."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import DOMAIN as DIAGNOSTICS_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "failing_method",
    ["async_get_lan_info", "async_get_diagnostics", "async_get_write_req_remaining"],
)
async def test_diagnostics_connection_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    failing_method: str,
) -> None:
    """Test that a connection error during diagnostics returns a 500 response."""
    getattr(mock_duco_client, failing_method).side_effect = DucoConnectionError(
        "Server disconnected"
    )
    assert await async_setup_component(hass, DIAGNOSTICS_DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{mock_config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR
