"""Tests for the Duco diagnostics."""

from dataclasses import replace
from http import HTTPStatus
from unittest.mock import AsyncMock

from duco_connectivity import ApiInfo, DucoConnectionError
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
    """Test that the full diagnostics payload matches the snapshot."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "failing_method",
    [
        "async_get_api_info",
        "async_get_lan_info",
        "async_get_diagnostics",
        "async_get_write_requests_remaining",
    ],
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


async def test_diagnostics_without_optional_software_version(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that an optional software version is omitted from diagnostics."""
    # BoardInfo is a frozen dataclass, so the mock must be updated before
    # integration setup — the coordinator stores board_info during async_setup.
    mock_duco_client.async_get_board_info.return_value = replace(
        mock_duco_client.async_get_board_info.return_value,
        software_version=None,
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["board_info"]["public_api_version"] == str(
        mock_duco_client.async_get_board_info.return_value.public_api_version
    )
    assert "software_version" not in diagnostics["board_info"]


@pytest.mark.usefixtures("init_integration")
async def test_diagnostics_without_optional_api_metadata(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test diagnostics when optional API metadata is absent."""
    mock_duco_client.async_get_api_info.return_value = ApiInfo(
        api_version=mock_duco_client.async_get_api_info.return_value.api_version
    )

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert diagnostics["api_info"] == {
        "public_api_version": str(
            mock_duco_client.async_get_api_info.return_value.api_version
        )
    }
