"""Test the EvolvIOT config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.evolviot.api import (
    EvolvIOTConnectionError,
    EvolvIOTDeviceAuthorizationPending,
)
from homeassistant.components.evolviot.const import (
    CONF_ACCESS_TOKEN,
    CONF_API_BASE_URL,
    CONF_REFRESH_TOKEN,
    CONF_VERIFY_SSL,
    DEFAULT_API_BASE_URL,
    DOMAIN,
    NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

PAIRING_PAYLOAD = {
    "device_code": "mock-device-code",
    "user_code": "MOCK-CODE",
    "qr_payload": "mock-qr-payload",
    "expires_in": 600,
}


async def test_pairing_success(hass: HomeAssistant) -> None:
    """Test a successful pairing flow."""
    with (
        patch(
            "homeassistant.components.evolviot.config_flow.EvolvIOTApi",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.evolviot.config_flow."
            "EvolvIOTConfigFlow._async_refresh_pairing_on_expiry",
            new_callable=AsyncMock,
        ),
    ):
        api = mock_api_class.return_value
        api.async_start_device_authorization = AsyncMock(return_value=PAIRING_PAYLOAD)
        api.async_exchange_device_code = AsyncMock(
            return_value={
                CONF_ACCESS_TOKEN: "mock-access-token",
                CONF_REFRESH_TOKEN: "mock-refresh-token",
            }
        )
        api.async_validate = AsyncMock(return_value={"user_id": "mock-user"})

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
                CONF_VERIFY_SSL: True,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == {
        CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
        CONF_ACCESS_TOKEN: "mock-access-token",
        CONF_REFRESH_TOKEN: "mock-refresh-token",
        CONF_VERIFY_SSL: True,
    }


async def test_pairing_pending(hass: HomeAssistant) -> None:
    """Test pending app approval keeps the flow on the pairing step."""
    with (
        patch(
            "homeassistant.components.evolviot.config_flow.EvolvIOTApi",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.evolviot.config_flow."
            "EvolvIOTConfigFlow._async_refresh_pairing_on_expiry",
            new_callable=AsyncMock,
        ),
    ):
        api = mock_api_class.return_value
        api.async_start_device_authorization = AsyncMock(return_value=PAIRING_PAYLOAD)
        api.async_exchange_device_code = AsyncMock(
            side_effect=EvolvIOTDeviceAuthorizationPending
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
                CONF_VERIFY_SSL: True,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "authorization_pending"}


async def test_pairing_start_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection failure while starting pairing."""
    with (
        patch(
            "homeassistant.components.evolviot.config_flow.EvolvIOTApi",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.evolviot.config_flow."
            "EvolvIOTConfigFlow._async_refresh_pairing_on_expiry",
            new_callable=AsyncMock,
        ),
    ):
        mock_api_class.return_value.async_start_device_authorization = AsyncMock(
            side_effect=EvolvIOTConnectionError
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_API_BASE_URL: DEFAULT_API_BASE_URL,
                CONF_VERIFY_SSL: True,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
