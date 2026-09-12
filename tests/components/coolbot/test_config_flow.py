"""Full coverage of the config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pycoolbot import CoolbotAuthError, CoolbotError
import pytest

from homeassistant.components.coolbot.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_EMAIL, TEST_PASSWORD, make_device

from tests.common import MockConfigEntry

USER_INPUT = {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: TEST_PASSWORD}


async def _start_user_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    return result


async def test_user_flow_creates_entry(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """A valid login creates an entry keyed to the account."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_EMAIL
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_EMAIL
    mock_client.async_close.assert_awaited()
    await hass.async_block_till_done()


async def test_user_flow_strips_and_lowercases_identity(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Whitespace and case never create a second entry for the same account."""
    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: f"  {TEST_EMAIL.upper()} ", CONF_PASSWORD: TEST_PASSWORD},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_EMAIL] == TEST_EMAIL.upper()
    assert result["result"].unique_id == TEST_EMAIL
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("connect_effect", "expected_error"),
    [
        (CoolbotAuthError("bad login"), "invalid_auth"),
        (CoolbotError("socket lost"), "cannot_connect"),
        (RuntimeError("surprise"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    connect_effect: Exception,
    expected_error: str,
) -> None:
    """Every failure shows the right error, and the flow stays usable."""
    mock_client.async_connect.side_effect = connect_effect

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_client.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_user_flow_rejects_account_with_no_devices(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """An account that never provisioned a CoolBot is refused."""
    mock_client.async_get_devices.return_value = [
        make_device(is_provisioned=False, mac_address=None)
    ]

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_user_flow_aborts_on_duplicate_account(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The same account cannot be added twice."""
    mock_config_entry.add_to_hass(hass)

    result = await _start_user_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
