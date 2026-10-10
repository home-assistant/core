"""Test the EvolvIOT config flow."""

from unittest.mock import AsyncMock, patch

from pyevolviot import (
    EvolvIOTApiError,
    EvolvIOTAuthError,
    EvolvIOTConnectionError,
    EvolvIOTData,
    EvolvIOTDeviceAuthorizationDenied,
    EvolvIOTDeviceAuthorizationExpired,
    EvolvIOTDeviceAuthorizationPending,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.evolviot.const import CONF_REFRESH_TOKEN, DOMAIN, NAME
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry

PAIRING_PAYLOAD = {
    "device_code": "mock-device-code",
    "user_code": "MOCK-CODE",
    "expires_in": 600,
    "interval": 0,
}
TOKEN_PAYLOAD = {
    CONF_ACCESS_TOKEN: "mock-access-token",
    CONF_REFRESH_TOKEN: "mock-refresh-token",
}


async def _async_start_flow(hass: HomeAssistant) -> FlowResult:
    """Start the EvolvIOT user flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def _async_finish_progress_flow(hass: HomeAssistant, flow_id: str) -> FlowResult:
    """Wait for and finish a progress flow."""
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


@pytest.mark.usefixtures("mock_connect_websocket")
async def test_pairing_success(hass: HomeAssistant) -> None:
    """Test a successful device authorization flow."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(return_value=TOKEN_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({"user_id": "mock-user"})),
        ),
    ):
        result = await _async_start_flow(hass)
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "user"
        assert result["progress_action"] == "pair"
        assert result["description_placeholders"] == {
            "user_code": "MOCK-CODE",
            "expires_in": "600",
        }
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_ACCESS_TOKEN: "mock-access-token",
        CONF_REFRESH_TOKEN: "mock-refresh-token",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "mock-user"


@pytest.mark.usefixtures("mock_connect_websocket")
async def test_pairing_waits_for_approval(hass: HomeAssistant) -> None:
    """Test device authorization polls until the user approves it."""
    exchange = AsyncMock(
        side_effect=[EvolvIOTDeviceAuthorizationPending, TOKEN_PAYLOAD]
    )
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch("pyevolviot.EvolvIOTApi.async_exchange_device_code", exchange),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({"user_id": "mock-user"})),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert exchange.await_count == 2


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(EvolvIOTConnectionError, "cannot_connect", id="cannot-connect"),
        pytest.param(EvolvIOTApiError, "unknown", id="unknown"),
    ],
)
async def test_pairing_start_error(
    hass: HomeAssistant,
    exception: type[EvolvIOTApiError],
    reason: str,
) -> None:
    """Test errors while starting device authorization."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_start_device_authorization",
        AsyncMock(side_effect=exception),
    ):
        result = await _async_start_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "pairing_payload",
    [
        pytest.param({}, id="empty"),
        pytest.param({"user_code": "MOCK-CODE"}, id="missing-device-code"),
        pytest.param({"device_code": "mock-device-code"}, id="missing-user-code"),
    ],
)
async def test_pairing_start_invalid_response(
    hass: HomeAssistant, pairing_payload: dict[str, str]
) -> None:
    """Test an invalid device authorization response."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_start_device_authorization",
        AsyncMock(return_value=pairing_payload),
    ):
        result = await _async_start_flow(hass)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


@pytest.mark.parametrize(
    ("exception", "reason"),
    [
        pytest.param(
            EvolvIOTDeviceAuthorizationExpired,
            "authorization_expired",
            id="expired",
        ),
        pytest.param(
            EvolvIOTDeviceAuthorizationDenied,
            "authorization_denied",
            id="denied",
        ),
        pytest.param(EvolvIOTAuthError, "invalid_auth", id="invalid-auth"),
        pytest.param(EvolvIOTConnectionError, "cannot_connect", id="cannot-connect"),
        pytest.param(EvolvIOTApiError, "unknown", id="unknown"),
    ],
)
async def test_pairing_error(
    hass: HomeAssistant,
    exception: type[EvolvIOTApiError],
    reason: str,
) -> None:
    """Test errors while completing device authorization."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(side_effect=exception),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    "token_data",
    [
        pytest.param({CONF_ACCESS_TOKEN: "mock-access-token"}, id="missing"),
        pytest.param(
            {CONF_ACCESS_TOKEN: "mock-access-token", CONF_REFRESH_TOKEN: None},
            id="null",
        ),
        pytest.param(
            {CONF_ACCESS_TOKEN: "mock-access-token", CONF_REFRESH_TOKEN: ""},
            id="empty",
        ),
        pytest.param(
            {CONF_ACCESS_TOKEN: "mock-access-token", CONF_REFRESH_TOKEN: "   "},
            id="whitespace",
        ),
    ],
)
async def test_pairing_invalid_refresh_token(
    hass: HomeAssistant, token_data: dict[str, str | None]
) -> None:
    """Test a token response without a usable refresh token."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(return_value=token_data),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_pairing_validation_error(hass: HomeAssistant) -> None:
    """Test an API error while validating the authorized account."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(return_value=TOKEN_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(side_effect=EvolvIOTApiError),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_pairing_missing_account_id(hass: HomeAssistant) -> None:
    """Test a successful pairing response without an account ID."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(return_value=TOKEN_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({})),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unknown"


async def test_account_already_configured(hass: HomeAssistant) -> None:
    """Test pairing an account that is already configured."""
    MockConfigEntry(domain=DOMAIN, unique_id="mock-user").add_to_hass(hass)
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(return_value=TOKEN_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({"user_id": "mock-user"})),
        ),
    ):
        result = await _async_start_flow(hass)
        result = await _async_finish_progress_flow(hass, result["flow_id"])

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
