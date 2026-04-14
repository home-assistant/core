"""Test the blanco config flow."""

import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from blanco_smart_home_api_client import ApiErrorCode

from homeassistant import config_entries
from homeassistant.components.blanco.const import (
    CONF_APP_ID,
    CONF_APP_LOCALE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_SERIAL,
    CONF_SERVICE_CODE,
    CONF_TOKEN,
    CONF_TOKEN_TYPE,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

# ── Test constants ─────────────────────────────────────────────────────────────

TEST_SERIAL = "SN123456"
TEST_SERVICE_CODE = "ABC-123"
TEST_TOKEN = "test-bearer-token"
TEST_APP_ID = "test-app-id"
TEST_DEV_TYPE = 1

# Expected SHA-256 dev_id derived from serial + service code
TEST_DEV_ID = hashlib.sha256((TEST_SERIAL + TEST_SERVICE_CODE).encode()).hexdigest()

# ── Mock response templates ────────────────────────────────────────────────────

# Response for POST /apps/registrations
APP_REG_RESPONSE = {
    "results": [{"app_id": TEST_APP_ID}],
    "errors": None,
    "info": None,
}

# Successful auth response for POST /auth/token
AUTH_RESPONSE = {
    "results": [
        {
            "token": TEST_TOKEN,
            "token_type": "Bearer",
            "dev_type": TEST_DEV_TYPE,
        }
    ],
    "errors": None,
    "info": None,
}


def make_mock_response(status: int = 200, json_data: dict | None = None) -> MagicMock:
    """Create a mock aiohttp response context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    mock_resp.json = AsyncMock(return_value=json_data or {})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def make_session(app_reg_response: MagicMock, auth_response: MagicMock) -> MagicMock:
    """Create a mock aiohttp session with two sequential POST responses.

    The config flow makes two POST requests in order:
      1. POST /apps/registrations  (app registration)
      2. POST /auth/token          (device authentication)
    """
    mock_session = MagicMock()
    mock_session.post.side_effect = [app_reg_response, auth_response]
    return mock_session


# ── Happy path ─────────────────────────────────────────────────────────────────


async def test_form_shows_empty_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that initialising the flow shows an empty form without errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful config flow: correct data stored and dev_id derived via SHA-256."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_SERIAL
    assert result["data"][CONF_SERIAL] == TEST_SERIAL
    assert result["data"][CONF_TOKEN] == TEST_TOKEN
    assert result["data"][CONF_TOKEN_TYPE] == "Bearer"
    assert result["data"][CONF_DEV_TYPE] == TEST_DEV_TYPE
    assert result["data"][CONF_DEV_ID] == TEST_DEV_ID
    assert result["data"][CONF_APP_ID] == TEST_APP_ID
    assert CONF_APP_LOCALE in result["data"]
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_auth_request_uses_correct_payload(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the auth POST sends the correct dev_id, service and headers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        session = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        mock_session_factory.return_value = session

        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    # Second POST call is the auth request
    auth_call = session.post.call_args_list[1]
    assert auth_call.kwargs["json"]["dev_id"] == TEST_DEV_ID
    assert auth_call.kwargs["json"]["service"] == 1
    assert auth_call.kwargs["headers"]["X-App-Id"] == TEST_APP_ID


# ── Error paths ────────────────────────────────────────────────────────────────


async def test_access_not_granted(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that HTTP 401 from the auth endpoint raises access_not_granted."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(status=401, json_data={"errors": [], "results": []}),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "access_not_granted"}


async def test_access_not_granted_recovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test recovery from access_not_granted by resubmitting valid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt: auth returns 401
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(status=401, json_data={"errors": [], "results": []}),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["errors"] == {"base": "access_not_granted"}

    # Second attempt: succeeds
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_device_type_not_supported(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that error code DEVICE_TYPE_NOT_SUPPORTED raises device_type_not_supported."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    error_body = {
        "results": [],
        "errors": [{"code": ApiErrorCode.DEVICE_TYPE_NOT_SUPPORTED}],
        "info": None,
    }

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(status=400, json_data=error_body),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "device_type_not_supported"}


async def test_invalid_auth_empty_token(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that a 200 auth response with no token raises invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(
                json_data={"results": [{}], "errors": None, "info": None}
            ),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect_client_error(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that aiohttp.ClientError raises cannot_connect, with successful recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt: network error
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError)
        cm.__aexit__ = AsyncMock(return_value=False)
        mock_session = MagicMock()
        mock_session.post.return_value = cm
        mock_session_factory.return_value = mock_session

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt: succeeds
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cannot_connect_non_200(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that a non-200 / non-401 auth response raises cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(status=500, json_data={"errors": [], "results": []}),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_duplicate_entry_aborted(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that configuring the same serial number twice aborts the second flow."""
    # First successful setup
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Second attempt with same serial: should abort
    result2 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_session_factory:
        mock_session_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


# ── Reauth flow ─────────────────────────────────────────────────────────────────


async def test_reauth_shows_confirm_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Reauth flow shows the reauth_confirm step after SOURCE_REAUTH."""
    # Create entry first through normal flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_factory:
        mock_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Trigger reauth
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_success(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Successful reauth updates the token and aborts with reauth_successful."""
    # Create entry first
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_factory:
        mock_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )
    assert result["step_id"] == "reauth_confirm"

    NEW_AUTH_RESPONSE = {
        "results": [
            {"token": "new-token", "token_type": "Bearer", "dev_type": TEST_DEV_TYPE}
        ],
        "errors": None,
        "info": None,
    }
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_factory:
        mock_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=NEW_AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERVICE_CODE: TEST_SERVICE_CODE}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_invalid_service_code(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Wrong service code during reauth shows access_not_granted error."""
    # Create entry first
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_factory:
        mock_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(json_data=AUTH_RESPONSE),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SERIAL: TEST_SERIAL, CONF_SERVICE_CODE: TEST_SERVICE_CODE},
        )
        await hass.async_block_till_done()

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=entry.data,
    )

    with patch(
        "homeassistant.components.blanco.config_flow.async_get_clientsession"
    ) as mock_factory:
        mock_factory.return_value = make_session(
            make_mock_response(json_data=APP_REG_RESPONSE),
            make_mock_response(status=401, json_data={"errors": [], "results": []}),
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_SERVICE_CODE: "WRONG-CODE"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "access_not_granted"}
