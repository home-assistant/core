"""Tests for Cielo config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from cieloconnectapi.exceptions import AuthenticationError
import pytest

from homeassistant.components.cielo_home.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_TOKEN = "valid-test-token"
MOCK_CIELO_CLIENT_CTOR = "homeassistant.components.cielo_home.config_flow.CieloClient"


def _devices_payload(parsed: dict | None) -> MagicMock:
    """Return a mock object shaped like cieloconnectapi get_devices_data() result."""
    payload = MagicMock()
    payload.raw = {}
    payload.parsed = parsed
    return payload


@pytest.mark.usefixtures("mock_setup_entry")
async def test_full_config_flow_success(hass: HomeAssistant) -> None:
    """Test successful config flow with valid API key."""
    mock_client = MagicMock()
    mock_client.user_id = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "  test-api-key  "},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cielo Home"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
        CONF_TOKEN: MOCK_TOKEN,
    }
    assert result["result"].unique_id == "test-user"


async def test_full_config_flow_abort_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the flow aborts when the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    mock_client = MagicMock()
    mock_client.user_id = mock_config_entry.unique_id
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("api_error", "flow_error_key"),
    [
        (ConnectionError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_error_mapping(
    hass: HomeAssistant, api_error: type[Exception], flow_error_key: str
) -> None:
    """Test we handle various API errors correctly.

    These errors may occur from either token retrieval or device fetch
    (your flow does both in validation).
    """
    mock_client = MagicMock()
    mock_client.user_id = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)
    mock_client.get_devices_data = AsyncMock(side_effect=api_error)

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == flow_error_key

        # simulate recovery (next call succeeds)
        mock_client.get_devices_data = AsyncMock(return_value=MagicMock(parsed=True))

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

        assert result3["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_error_mapping_invalid_auth(hass: HomeAssistant) -> None:
    """Test AuthenticationError maps to invalid_auth."""

    mock_client = MagicMock()
    mock_client.user_id = "test-user"
    mock_client.get_or_refresh_token = AsyncMock(side_effect=AuthenticationError)
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_auth"

        mock_client.get_or_refresh_token = AsyncMock(return_value=MOCK_TOKEN)

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "test-api-key"},
        )

    assert result3["type"] is FlowResultType.CREATE_ENTRY


def _mock_client(user_id: str = "test-user-1") -> MagicMock:
    """Return a mock CieloClient that validates successfully."""
    mock_client = MagicMock()
    mock_client.user_id = user_id
    mock_client.get_or_refresh_token = AsyncMock(return_value="new-token")
    mock_client.get_devices_data = AsyncMock(
        return_value=_devices_payload({"dev1": MagicMock()})
    )
    return mock_client


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication updates the API key and token."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=_mock_client()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "  new-api-key  "},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "new-api-key",
        CONF_TOKEN: "new-token",
    }


@pytest.mark.parametrize(
    ("method", "side_effect", "devices", "error"),
    [
        pytest.param(
            "get_or_refresh_token",
            AuthenticationError,
            {"dev1": MagicMock()},
            "invalid_auth",
            id="invalid_auth",
        ),
        pytest.param(
            "get_devices_data",
            ConnectionError,
            {"dev1": MagicMock()},
            "cannot_connect",
            id="cannot_connect",
        ),
        pytest.param(
            "get_devices_data",
            Exception,
            {"dev1": MagicMock()},
            "unknown",
            id="unknown",
        ),
        pytest.param(
            "get_devices_data",
            None,
            {},
            "no_devices",
            id="no_devices",
        ),
    ],
)
@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    method: str,
    side_effect: type[Exception] | None,
    devices: dict[str, MagicMock],
    error: str,
) -> None:
    """Test reauthentication errors and recovery."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_client = _mock_client()
    mock_client.get_devices_data.return_value = _devices_payload(devices)
    getattr(mock_client, method).side_effect = side_effect

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=_mock_client()):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_API_KEY: "new-api-key",
        CONF_TOKEN: "new-token",
    }


async def test_reauth_flow_wrong_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauthentication aborts when the API key belongs to another account."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    with patch(MOCK_CIELO_CLIENT_CTOR, return_value=_mock_client("other-user")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_KEY: "new-api-key"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert mock_config_entry.data == {
        CONF_API_KEY: "test-api-key-",
        CONF_TOKEN: "valid-test-token",
    }
