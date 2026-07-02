"""Test the gentex_place config flow."""

from unittest.mock import MagicMock

import botocore.exceptions
import pytest

from homeassistant import config_entries
from homeassistant.components.gentex_place.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import INVALID_TEST_ACCESS_JWT, TEST_CREDENTIALS, TEST_UNIQUE_ID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("aioclient_mock_fixture", "mock_setup_entry")
async def test_full_flow(
    hass: HomeAssistant,
    mock_login: MagicMock,
) -> None:
    """Test the full SRP authentication flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Place"
    assert result["data"]["token"]["access_token"] is not None
    assert result["data"]["token"]["id_token"] == "mock-id-token"
    assert result["result"].unique_id == TEST_UNIQUE_ID
    mock_login.assert_called_once()


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_login",
    "mock_setup_entry",
)
async def test_unique_configurations(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that duplicate configurations are rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_setup_entry",
)
async def test_login_client_error(
    hass: HomeAssistant,
    mock_login: MagicMock,
) -> None:
    """Test handling of botocore ClientError during login."""
    mock_login.side_effect = botocore.exceptions.ClientError(
        {"Error": {"Code": "NotAuthorizedException", "Message": "Bad creds"}},
        "InitiateAuth",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "srp_auth_failed"}


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_setup_entry",
)
async def test_login_unknown_error(
    hass: HomeAssistant,
    mock_login: MagicMock,
) -> None:
    """Test error handling for unexpected login failures."""
    mock_login.side_effect = Exception("unexpected")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_setup_entry",
    "mock_login",
)
async def test_reauth_successful(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_setup_entry",
    "mock_login",
)
@pytest.mark.parametrize("mock_srp_access_token", [INVALID_TEST_ACCESS_JWT])
async def test_reauth_unique_id_mismatch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that reauth fails when the unique ID does not match."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
