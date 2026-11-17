"""Test the gentex_place config flow."""

from unittest.mock import MagicMock

from place.errors import (
    PlaceInvalidCredentialsError,
    PlaceLoginConnectionError,
    PlaceLoginError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.gentex_place.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_CREDENTIALS, TEST_ID_JWT, TEST_UNIQUE_ID


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
    assert result["data"]["token"]["id_token"] == TEST_ID_JWT
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
@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(PlaceInvalidCredentialsError(), "invalid_auth", id="invalid_auth"),
        pytest.param(
            PlaceLoginConnectionError(), "cannot_connect", id="cannot_connect"
        ),
    ],
)
async def test_login_error(
    hass: HomeAssistant,
    mock_login: MagicMock,
    error: Exception,
    expected: str,
) -> None:
    """Test handling of expected login failures and retrying."""
    mock_login.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected}

    mock_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures(
    "aioclient_mock_fixture",
    "mock_setup_entry",
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(PlaceLoginError("service error"), id="unexpected_service_error"),
        pytest.param(Exception("unexpected"), id="unexpected_error"),
    ],
)
async def test_login_unknown_error(
    hass: HomeAssistant,
    mock_login: MagicMock,
    error: Exception,
) -> None:
    """Test error handling for unexpected login failures."""
    mock_login.side_effect = error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}

    mock_login.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=TEST_CREDENTIALS,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
