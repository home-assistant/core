"""Test the Schlage config flow."""

from unittest.mock import AsyncMock, Mock

from pyschlage.exceptions import Error as PyschlageError, NotAuthorizedError
import pytest

from homeassistant import config_entries
from homeassistant.components.schlage.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_pyschlage_auth: Mock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-username"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_pyschlage_auth: Mock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pyschlage_auth.authenticate.side_effect = NotAuthorizedError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_unknown(hass: HomeAssistant, mock_pyschlage_auth: Mock) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_pyschlage_auth.authenticate.side_effect = PyschlageError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test reauth flow."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "new-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_invalid_auth(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test reauth flow."""
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    mock_pyschlage_auth.authenticate.reset_mock()
    mock_pyschlage_auth.authenticate.side_effect = NotAuthorizedError
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_wrong_account(
    hass: HomeAssistant,
    mock_added_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
    mock_pyschlage_auth: Mock,
) -> None:
    """Test reauth flow."""
    mock_pyschlage_auth.user_id = "bad-user-id"
    mock_added_config_entry.async_start_reauth(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    [result] = flows
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"password": "new-password"},
    )
    await hass.async_block_till_done()

    mock_pyschlage_auth.authenticate.assert_called_once_with()
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "wrong_account"
    assert mock_added_config_entry.data == {
        "username": "asdf@asdf.com",
        "password": "hunter2",
    }
    assert len(mock_setup_entry.mock_calls) == 1
