"""Test the Electra Smart config flow."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from json import loads
from unittest.mock import patch

from pytest_homeassistant.common import MockConfigEntry, async_load_fixture

from homeassistant import config_entries
from homeassistant.components.electrasmart.config_flow import ElectraApiError
from homeassistant.components.electrasmart.const import (
    CONF_IMEI,
    CONF_OTP,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo


@asynccontextmanager
async def _patch_success(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Patch the Electra API to accept the phone number and OTP."""
    mock_generate_token = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    mock_otp_response = loads(
        await async_load_fixture(hass, "otp_response.json", DOMAIN)
    )
    with (
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token,
        ),
        patch(
            "electrasmart.api.ElectraAPI.validate_one_time_password",
            return_value=mock_otp_response,
        ),
        patch("electrasmart.api.ElectraAPI.fetch_devices", return_value=[]),
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test user config."""

    mock_generate_token = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        return_value=mock_generate_token,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=None,
        )

        assert result["step_id"] == "user"

        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_OTP


async def test_one_time_password(hass: HomeAssistant) -> None:
    """Test one time password."""

    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )

        # test with required
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "0521234567"


async def test_one_time_password_api_error(hass: HomeAssistant) -> None:
    """Test one time password."""
    mock_generate_token = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    with (
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token,
        ),
        patch(
            "electrasmart.api.ElectraAPI.validate_one_time_password",
            side_effect=ElectraApiError,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )

    assert result["type"] is FlowResultType.FORM


async def test_cannot_connect(hass: HomeAssistant) -> None:
    """Test cannot connect."""

    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        side_effect=ElectraApiError,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_phone_number(hass: HomeAssistant) -> None:
    """Test invalid phone number."""

    mock_invalid_phone_number_response = loads(
        await async_load_fixture(hass, "invalid_phone_number_response.json", DOMAIN)
    )

    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        return_value=mock_invalid_phone_number_response,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "invalid_phone_number"}

    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth."""

    mock_generate_token_response = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    mock_invalid_otp_response = loads(
        await async_load_fixture(hass, "invalid_otp_response.json", DOMAIN)
    )

    with (
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token_response,
        ),
        patch(
            "electrasmart.api.ElectraAPI.validate_one_time_password",
            return_value=mock_invalid_otp_response,
        ),
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_PHONE_NUMBER: "0521234567"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_OTP
    assert result["errors"] == {CONF_OTP: "invalid_auth"}

    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reauth(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test reauthentication of a locked out account."""
    config_entry.add_to_hass(hass)

    async with _patch_success(hass):
        result = await config_entry.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_OTP

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert config_entry.data[CONF_TOKEN] == "ec7a0db6c1f148ca8c0f48aabb5f8150"


async def test_reauth_confirm_does_not_request_a_code(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that showing the confirmation does not send a one-time password."""
    config_entry.add_to_hass(hass)

    with patch("electrasmart.api.ElectraAPI.generate_new_token") as generate_new_token:
        result = await config_entry.start_reauth_flow(hass)

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert generate_new_token.call_count == 0

        # The dialog is fetched again every time it is opened or refreshed.
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert generate_new_token.call_count == 0


async def test_reauth_generate_token_failure_can_be_retried(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a failed request for a one-time password can be retried."""
    config_entry.add_to_hass(hass)

    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        side_effect=ElectraApiError("Failed to connect to API"),
    ):
        result = await config_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "cannot_connect"}

    # Once the API answers again, the same form asks for the code.
    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_OTP

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_rejected_phone_number_can_be_retried(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a phone number the API refuses keeps the confirmation."""
    config_entry.add_to_hass(hass)

    # The API answers, but refuses to send a code to the number.
    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        return_value={"status": 0, "data": {"res": 1}},
    ):
        result = await config_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {"base": "invalid_phone_number"}

    # The number the entry already holds is accepted on the next attempt.
    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_OTP

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_invalid_otp(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test a rejected one-time password, then a successful retry."""
    config_entry.add_to_hass(hass)

    mock_invalid_otp_response = loads(
        await async_load_fixture(hass, "invalid_otp_response.json", DOMAIN)
    )
    mock_generate_token = loads(
        await async_load_fixture(hass, "generate_token_response.json", DOMAIN)
    )
    with (
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token,
        ),
        patch(
            "electrasmart.api.ElectraAPI.validate_one_time_password",
            return_value=mock_invalid_otp_response,
        ),
    ):
        result = await config_entry.start_reauth_flow(hass)

        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

        assert result["step_id"] == CONF_OTP

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == CONF_OTP
        assert result["errors"] == {CONF_OTP: "invalid_auth"}

        flow_id = result["flow_id"]

    # The user can recover by entering a one-time password that is accepted.
    async with _patch_success(hass):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {CONF_OTP: "1234"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_dhcp_discovery(hass: HomeAssistant) -> None:
    """Test a flow started by DHCP discovery."""
    async with _patch_success(hass):
        with patch(
            "homeassistant.components.electrasmart.config_flow.generate_imei",
            return_value="123456789012345",
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_DHCP},
                data=DhcpServiceInfo(
                    ip="192.0.2.10",
                    hostname="elrssid123456",
                    macaddress="aabbcc123456",
                ),
            )

            assert result["type"] is FlowResultType.FORM
            assert result["step_id"] == "user"

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_PHONE_NUMBER: "0521234567"},
            )

            assert result["step_id"] == CONF_OTP

            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_OTP: "1234"}
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "0521234567"
    assert result["result"].data == {
        CONF_TOKEN: "ec7a0db6c1f148ca8c0f48aabb5f8150",
        CONF_IMEI: "123456789012345",
        CONF_PHONE_NUMBER: "0521234567",
    }


async def test_dhcp_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test DHCP discovery aborts when an account is already configured."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0521234567",
        data={
            CONF_PHONE_NUMBER: "0521234567",
            CONF_OTP: "1234",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="elrssid123456",
            macaddress="aabbcc123456",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_already_in_progress(hass: HomeAssistant) -> None:
    """Test a second DHCP discovery aborts while one is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.10",
            hostname="elrssid123456",
            macaddress="aabbcc123456",
        ),
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=DhcpServiceInfo(
            ip="192.0.2.11",
            hostname="elrssid123457",
            macaddress="aabbcc123457",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"
