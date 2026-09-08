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
from homeassistant.components.evolviot.const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DOMAIN,
    NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

PAIRING_PAYLOAD = {
    "device_code": "mock-device-code",
    "user_code": "MOCK-CODE",
    "expires_in": 600,
}


async def test_pairing_success(hass: HomeAssistant) -> None:
    """Test a successful pairing flow."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(
                return_value={
                    CONF_ACCESS_TOKEN: "mock-access-token",
                    CONF_REFRESH_TOKEN: "mock-refresh-token",
                }
            ),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({"user_id": "mock-user"})),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {}
        assert result["description_placeholders"] == {
            "user_code": "MOCK-CODE",
            "expires_in": "600",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_ACCESS_TOKEN: "mock-access-token",
        CONF_REFRESH_TOKEN: "mock-refresh-token",
        CONF_VERIFY_SSL: True,
    }
    assert result["result"].unique_id == "mock-user"


async def test_pairing_pending(hass: HomeAssistant) -> None:
    """Test pending app approval keeps the flow on the pairing step."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(side_effect=EvolvIOTDeviceAuthorizationPending),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "authorization_pending"}


async def test_pairing_start_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure while starting pairing."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_start_device_authorization",
        AsyncMock(side_effect=EvolvIOTConnectionError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_pairing_start_unknown_error(hass: HomeAssistant) -> None:
    """Test an API failure while starting pairing."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_start_device_authorization",
        AsyncMock(side_effect=EvolvIOTApiError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


async def test_pairing_start_empty_response(hass: HomeAssistant) -> None:
    """Test an empty response while starting pairing."""
    with patch(
        "pyevolviot.EvolvIOTApi.async_start_device_authorization",
        AsyncMock(return_value={}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.parametrize(
    ("exception", "step_id", "error"),
    [
        pytest.param(
            EvolvIOTDeviceAuthorizationExpired,
            "user",
            "authorization_expired",
            id="expired",
        ),
        pytest.param(
            EvolvIOTDeviceAuthorizationDenied,
            "user",
            "authorization_denied",
            id="denied",
        ),
        pytest.param(
            EvolvIOTAuthError,
            "user",
            "invalid_auth",
            id="invalid-auth",
        ),
        pytest.param(
            EvolvIOTConnectionError,
            "pair",
            "cannot_connect",
            id="cannot-connect",
        ),
        pytest.param(
            EvolvIOTApiError,
            "pair",
            "unknown",
            id="unknown",
        ),
    ],
)
async def test_pairing_errors(
    hass: HomeAssistant,
    exception: type[EvolvIOTApiError],
    step_id: str,
    error: str,
) -> None:
    """Test errors while completing pairing."""
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
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == {"base": error}


async def test_pairing_validation_unknown_error(hass: HomeAssistant) -> None:
    """Test an API failure while validating the paired account."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(
                return_value={
                    CONF_ACCESS_TOKEN: "mock-access-token",
                    CONF_REFRESH_TOKEN: "mock-refresh-token",
                }
            ),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(side_effect=EvolvIOTApiError),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "unknown"}


async def test_pairing_missing_account_id(hass: HomeAssistant) -> None:
    """Test a successful pairing response without an account ID."""
    with (
        patch(
            "pyevolviot.EvolvIOTApi.async_start_device_authorization",
            AsyncMock(return_value=PAIRING_PAYLOAD),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_exchange_device_code",
            AsyncMock(
                return_value={
                    CONF_ACCESS_TOKEN: "mock-access-token",
                    CONF_REFRESH_TOKEN: "mock-refresh-token",
                }
            ),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({})),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "unknown"}


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
            AsyncMock(
                return_value={
                    CONF_ACCESS_TOKEN: "mock-access-token",
                    CONF_REFRESH_TOKEN: "mock-refresh-token",
                }
            ),
        ),
        patch(
            "pyevolviot.EvolvIOTApi.async_validate_data",
            AsyncMock(return_value=EvolvIOTData.from_payload({"user_id": "mock-user"})),
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
