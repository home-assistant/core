"""Test the WireGuard config flow."""
from unittest.mock import AsyncMock, MagicMock

from ha_wireguard_api.exceptions import (
    WireGuardException,
    WireGuardInvalidJson,
    WireGuardResponseError,
    WireGuardTimeoutError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.wireguard.const import DEFAULT_HOST, DEFAULT_NAME, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    mock_config_flow: MagicMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: DEFAULT_HOST},
    )
    await hass.async_block_till_done()
    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == DEFAULT_NAME
    assert result2.get("data") == {CONF_HOST: DEFAULT_HOST}
    assert len(mock_config_flow.get_peers.mock_calls) == 1
    assert len(setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "message", "error"),
    [
        (
            WireGuardTimeoutError,
            "Timeout occurred while connecting to WireGuard status API",
            "timeout_connect",
        ),
        (
            WireGuardResponseError,
            "Unexpected status from WireGuard status API",
            "cannot_connect",
        ),
        (
            WireGuardResponseError,
            "Unexpected content from WireGuard status API",
            "cannot_connect",
        ),
        (
            WireGuardInvalidJson,
            "Invalid JSON",
            "invalid_response",
        ),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    setup_entry: AsyncMock,
    mock_config_flow: MagicMock,
    side_effect: WireGuardException,
    message: str,
    error: str,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("step_id") == "user"
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    mock_config_flow.get_peers.side_effect = side_effect(message)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: DEFAULT_HOST},
    )
    await hass.async_block_till_done()
    assert result2.get("step_id") == "user"
    assert result2.get("type") == FlowResultType.FORM
    assert result2["errors"] == {"base": error}
    assert len(mock_config_flow.get_peers.mock_calls) == 1

    mock_config_flow.get_peers.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: DEFAULT_HOST},
    )
    await hass.async_block_till_done()
    assert result3.get("type") == FlowResultType.CREATE_ENTRY
    assert result3.get("title") == DEFAULT_NAME
    assert result3.get("data") == {CONF_HOST: DEFAULT_HOST}
    assert len(mock_config_flow.get_peers.mock_calls) == 2
    assert len(setup_entry.mock_calls) == 1
