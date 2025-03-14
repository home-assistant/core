"""Test the Weheat config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectorError
from aiohttp.client_reqrep import ConnectionKey
import pytest

from homeassistant.components.weheat.const import (
    DOMAIN,
    ENTRY_TITLE,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_SOURCE, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CLIENT_ID,
    CONF_AUTH_IMPLEMENTATION,
    CONF_REFRESH_TOKEN,
    MOCK_ACCESS_TOKEN,
    MOCK_REFRESH_TOKEN,
    USER_UUID_1,
    USER_UUID_2,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_user_id: AsyncMock,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_setup_entry,
) -> None:
    """Check full of adding a single heat pump."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    await handle_oauth(hass, hass_client_no_auth, aioclient_mock, result)

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_user_id.mock_calls) == 1

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == USER_UUID_1
    assert result["result"].title == ENTRY_TITLE
    assert result["data"][CONF_TOKEN][CONF_REFRESH_TOKEN] == MOCK_REFRESH_TOKEN
    assert result["data"][CONF_TOKEN][CONF_ACCESS_TOKEN] == MOCK_ACCESS_TOKEN
    assert result["data"][CONF_AUTH_IMPLEMENTATION] == DOMAIN


@pytest.mark.usefixtures("current_request_with_host")
async def test_duplicate_unique_id(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_user_id: AsyncMock,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_setup_entry,
) -> None:
    """Check that the config flow is aborted when an entry with the same ID exists."""
    result = await handle_pre_config_flow_test_setup(
        hass, hass_client_no_auth, aioclient_mock
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("get_user_id_from_token_exception", "expected_reason"),
    [
        (
            ClientConnectorError(
                ConnectionKey("", 0, False, False, None, None, None), OSError()
            ),
            "get_user_failed",
        ),
        (Exception, "unknown"),
    ],
)
async def test_get_user_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    mock_user_id: AsyncMock,
    get_user_id_from_token_exception: Exception,
    expected_reason: str,
) -> None:
    """Check that the config flow is aborted when getting the user ID results in an HTTP error or different exception."""
    result = await handle_pre_config_flow_test_setup(
        hass, hass_client_no_auth, aioclient_mock
    )

    mock_user_id.side_effect = get_user_id_from_token_exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("get_heat_pump_exception", "expected_reason"),
    [
        (
            ClientConnectorError(
                ConnectionKey("", 0, False, False, None, None, None), OSError()
            ),
            "get_heat_pumps_failed",
        ),
        (Exception, "unknown"),
    ],
)
async def test_get_heat_pumps_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    mock_user_id: AsyncMock,
    get_heat_pump_exception: Exception,
    expected_reason: str,
) -> None:
    """Check that the config flow is aborted when getting the heat pumps for this results in an HTTP error or different exception."""
    result = await handle_pre_config_flow_test_setup(
        hass, hass_client_no_auth, aioclient_mock
    )

    with (
        patch(
            "homeassistant.components.weheat.config_flow.HeatPumpDiscovery.async_discover_active",
            side_effect=get_heat_pump_exception,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("current_request_with_host")
async def test_get_no_heat_pumps_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    mock_user_id: AsyncMock,
) -> None:
    """Check that the config flow is aborted when the used does not have access to any heat pump."""
    result = await handle_pre_config_flow_test_setup(
        hass, hass_client_no_auth, aioclient_mock
    )

    with (
        patch(
            "homeassistant.components.weheat.config_flow.HeatPumpDiscovery.async_discover_active",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_heat_pumps"


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("get_heat_pump_data_exception", "expected_reason"),
    [
        (
            ClientConnectorError(
                ConnectionKey("", 0, False, False, None, None, None), OSError()
            ),
            "get_heat_pump_data_failed",
        ),
        (Exception, "unknown"),
    ],
)
async def test_get_heat_pump_data_error(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    mock_user_id: AsyncMock,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    get_heat_pump_data_exception: Exception,
    expected_reason: str,
) -> None:
    """Check that the config flow is aborted when getting the heat pump data results in an HTTP error or different exception."""
    result = await handle_pre_config_flow_test_setup(
        hass, hass_client_no_auth, aioclient_mock
    )

    mock_weheat_heat_pump.async_get_status.side_effect = get_heat_pump_data_exception

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # only care that the config flow is aborted
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("logged_in_user", "expected_reason"),
    [(USER_UUID_1, "reauth_successful"), (USER_UUID_2, "wrong_account")],
)
async def test_reauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    mock_user_id: AsyncMock,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    setup_credentials,
    logged_in_user: str,
    expected_reason: str,
) -> None:
    """Check reauth flow both with and without the correct logged in user."""
    mock_user_id.return_value = logged_in_user
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=USER_UUID_1,
    )

    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        flow_id=result["flow_id"],
        user_input={},
    )

    await handle_oauth(hass, hass_client_no_auth, aioclient_mock, result)

    assert result["type"] is FlowResultType.EXTERNAL_STEP

    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == expected_reason
    assert entry.unique_id == USER_UUID_1


async def handle_pre_config_flow_test_setup(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> ConfigFlowResult:
    """Handle the pre-test setup."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        unique_id=USER_UUID_1,
    )

    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )

    await handle_oauth(hass, hass_client_no_auth, aioclient_mock, result)

    return result


async def handle_oauth(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    result: ConfigFlowResult,
) -> None:
    """Handle the Oauth2 part of the flow."""
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=openid+offline_access"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": MOCK_REFRESH_TOKEN,
            "access_token": MOCK_ACCESS_TOKEN,
            "type": "Bearer",
            "expires_in": 60,
        },
    )
