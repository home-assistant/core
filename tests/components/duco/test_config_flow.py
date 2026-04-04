"""Tests for the Duco config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import BoardInfo, LanInfo
import pytest

from homeassistant import config_entries
from homeassistant.components.duco.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_MAC, USER_INPUT


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_duco_client: AsyncMock,
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.duco.config_flow.DucoClient",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.async_get_board_info = AsyncMock(return_value=mock_board_info)
        client.async_get_lan_info = AsyncMock(return_value=mock_lan_info)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SILENT_CONNECT"
    assert result["data"] == USER_INPUT

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].unique_id == TEST_MAC


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (DucoConnectionError("Connection refused"), "cannot_connect"),
        (DucoError("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test handling of connection and unknown errors in the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.duco.config_flow.DucoClient",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.async_get_board_info = AsyncMock(side_effect=exception)

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that a duplicate config entry is aborted."""
    # First config entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.duco.config_flow.DucoClient",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.async_get_board_info = AsyncMock(return_value=mock_board_info)
        client.async_get_lan_info = AsyncMock(return_value=mock_lan_info)
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
        await hass.async_block_till_done()

    # Second attempt for the same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.duco.config_flow.DucoClient",
        autospec=True,
    ) as mock_class:
        client = mock_class.return_value
        client.async_get_board_info = AsyncMock(return_value=mock_board_info)
        client.async_get_lan_info = AsyncMock(return_value=mock_lan_info)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
