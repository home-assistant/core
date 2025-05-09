"""Tests for the TotalConnect config flow."""

from unittest.mock import patch

from total_connect_client.exceptions import AuthenticationError

from homeassistant.components.totalconnect.const import (
    AUTO_BYPASS,
    CODE_REQUIRED,
    CONF_USERCODES,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .common import (
    CONFIG_DATA,
    CONFIG_DATA_NO_USERCODES,
    RESPONSE_DISARMED,
    RESPONSE_GET_ZONE_DETAILS_SUCCESS,
    RESPONSE_PARTITION_DETAILS,
    RESPONSE_SESSION_DETAILS,
    RESPONSE_SUCCESS,
    RESPONSE_USER_CODE_INVALID,
    TOTALCONNECT_GET_CONFIG,
    TOTALCONNECT_REQUEST,
    TOTALCONNECT_REQUEST_TOKEN,
    USERNAME,
    init_integration,
)

from tests.common import MockConfigEntry


async def test_user(hass: HomeAssistant) -> None:
    """Test user step."""
    # user starts with no data entered, so show the user form
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=None,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_show_locations(hass: HomeAssistant) -> None:
    """Test user locations form."""
    # user/pass provided, so check if valid then ask for usercodes on locations form
    responses = [
        RESPONSE_SESSION_DETAILS,
        RESPONSE_PARTITION_DETAILS,
        RESPONSE_GET_ZONE_DETAILS_SUCCESS,
        RESPONSE_DISARMED,
        RESPONSE_USER_CODE_INVALID,
        RESPONSE_SUCCESS,
    ]

    with (
        patch(
            TOTALCONNECT_REQUEST,
            side_effect=responses,
        ) as mock_request,
        patch(TOTALCONNECT_GET_CONFIG, side_effect=None),
        patch(TOTALCONNECT_REQUEST_TOKEN, side_effect=None),
        patch(
            "homeassistant.components.totalconnect.async_setup_entry", return_value=True
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_NO_USERCODES,
        )

        # first it should show the locations form
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "locations"
        # client should have sent four requests for init
        assert mock_request.call_count == 4

        # user enters an invalid usercode
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERCODES: "bad"},
        )
        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "locations"
        # client should have sent 5th request to validate usercode
        assert mock_request.call_count == 5

        # user enters a valid usercode
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            user_input={CONF_USERCODES: "7890"},
        )
        assert result3["type"] is FlowResultType.CREATE_ENTRY
        # client should have sent another request to validate usercode
        assert mock_request.call_count == 6


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test abort if the account is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=USERNAME,
    ).add_to_hass(hass)

    # Should fail, same USERNAME (flow)
    with patch("homeassistant.components.totalconnect.config_flow.TotalConnectClient"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass: HomeAssistant) -> None:
    """Test when we have errors during login."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient"
    ) as client_mock:
        client_mock.side_effect = AuthenticationError()
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
        unique_id=USERNAME,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.components.totalconnect.config_flow.TotalConnectClient"
        ) as client_mock,
        patch(
            "homeassistant.components.totalconnect.async_setup_entry", return_value=True
        ),
    ):
        # first test with an invalid password
        client_mock.side_effect = AuthenticationError()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_auth"}

        # now test with the password valid
        client_mock.side_effect = None

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries()) == 1


async def test_no_locations(hass: HomeAssistant) -> None:
    """Test with no user locations."""
    responses = [
        RESPONSE_SESSION_DETAILS,
        RESPONSE_PARTITION_DETAILS,
        RESPONSE_GET_ZONE_DETAILS_SUCCESS,
        RESPONSE_DISARMED,
    ]

    with (
        patch(
            TOTALCONNECT_REQUEST,
            side_effect=responses,
        ) as mock_request,
        patch(TOTALCONNECT_GET_CONFIG, side_effect=None),
        patch(TOTALCONNECT_REQUEST_TOKEN, side_effect=None),
        patch(
            "homeassistant.components.totalconnect.async_setup_entry", return_value=True
        ),
        patch(
            "homeassistant.components.totalconnect.TotalConnectClient.get_number_locations",
            return_value=0,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONFIG_DATA_NO_USERCODES,
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "no_locations"
        await hass.async_block_till_done()

        assert mock_request.call_count == 1


async def test_options_flow(hass: HomeAssistant) -> None:
    """Test config flow options."""
    config_entry = await init_integration(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={AUTO_BYPASS: True, CODE_REQUIRED: False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options == {AUTO_BYPASS: True, CODE_REQUIRED: False}
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
