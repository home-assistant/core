"""Tests for the Duco diagnostics."""

from dataclasses import replace
from http import HTTPStatus
from unittest.mock import AsyncMock

from duco_connectivity import ApiInfo
from duco_connectivity.exceptions import (
    DucoConnectionError,
    DucoError,
    DucoResponseError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.diagnostics import DOMAIN as DIAGNOSTICS_DOMAIN
from homeassistant.components.duco.diagnostics import async_get_config_entry_diagnostics
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

CLIENT_ERROR_CASES = [
    pytest.param(
        "async_get_api_info",
        DucoConnectionError("Server disconnected"),
        "connection_error",
        id="api-info-connection-error",
    ),
    pytest.param(
        "async_get_lan_info",
        DucoConnectionError("Server disconnected"),
        "connection_error",
        id="lan-info-connection-error",
    ),
    pytest.param(
        "async_get_diagnostics",
        DucoResponseError(500, "/info", "bad response"),
        "api_error",
        id="diagnostics-response-error",
    ),
    pytest.param(
        "async_get_write_requests_remaining",
        DucoResponseError(500, "/info", "bad response"),
        "api_error",
        id="write-budget-response-error",
    ),
]


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
    ("failing_method", "raised_error", "translation_key"),
    CLIENT_ERROR_CASES,
)
async def test_diagnostics_client_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    failing_method: str,
    raised_error: DucoError,
    translation_key: str,
) -> None:
    """Test that client errors during diagnostics return a 500 response."""
    del translation_key
    getattr(mock_duco_client, failing_method).side_effect = raised_error
    assert await async_setup_component(hass, DIAGNOSTICS_DOMAIN, {})
    await hass.async_block_till_done()
    client = await hass_client()
    response = await client.get(
        f"/api/diagnostics/config_entry/{mock_config_entry.entry_id}"
    )
    assert response.status == HTTPStatus.INTERNAL_SERVER_ERROR


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("failing_method", "raised_error", "translation_key"),
    CLIENT_ERROR_CASES,
)
async def test_diagnostics_client_error_translation_key(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    failing_method: str,
    raised_error: DucoError,
    translation_key: str,
) -> None:
    """Test that diagnostics client errors map to the expected translation key."""
    getattr(mock_duco_client, failing_method).side_effect = raised_error

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert exc_info.value.translation_key == translation_key


async def test_diagnostics_without_optional_software_version(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that an optional software version is omitted from diagnostics."""
    # BoardInfo is a frozen dataclass, so the mock must be updated before
    # integration setup - the coordinator stores board_info during async_setup.
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
