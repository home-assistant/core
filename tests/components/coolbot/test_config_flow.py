"""Full coverage of the config flow: user, reauth, and reconfigure paths."""

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


async def test_reauth_flow_updates_password(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reauth stores the replacement password on the existing entry."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_rejects_bad_password_then_recovers(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A wrong replacement password re-prompts instead of aborting."""
    mock_config_entry.add_to_hass(hass)
    mock_client.async_connect.side_effect = CoolbotAuthError("still wrong")

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "still-wrong"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    mock_client.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PASSWORD: "right-this-time"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "right-this-time"


async def test_reconfigure_flow_updates_credentials(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Reconfigure lets the user rotate the password in place."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: "rotated"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "rotated"


async def test_reconfigure_flow_refuses_a_different_account(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Pointing an entry at another account would orphan its entities."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: "other@example.com", CONF_PASSWORD: "pw"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "account_mismatch"
    assert mock_config_entry.data[CONF_EMAIL] == TEST_EMAIL


async def test_reconfigure_flow_shows_errors_then_recovers(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A transient outage during reconfigure re-prompts instead of aborting."""
    mock_config_entry.add_to_hass(hass)
    mock_client.async_connect.side_effect = CoolbotError("down")

    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: "pw"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_client.async_connect.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_EMAIL: TEST_EMAIL, CONF_PASSWORD: "pw"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
