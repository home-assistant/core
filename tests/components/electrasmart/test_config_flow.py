"""Test the Electra Smart config flow."""

from json import loads
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.electrasmart.config_flow import ElectraApiError
from homeassistant.components.electrasmart.const import (
    CONF_OTP,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import load_fixture


async def test_form(hass: HomeAssistant) -> None:
    """Test user config."""

    mock_generate_token = loads(load_fixture("generate_token_response.json", DOMAIN))
    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        return_value=mock_generate_token,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=None,
        )

        assert result["step_id"] == "user"

        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_OTP


async def test_one_time_password(hass: HomeAssistant) -> None:
    """Test one time password."""

    mock_generate_token = loads(load_fixture("generate_token_response.json", DOMAIN))
    mock_otp_response = loads(load_fixture("otp_response.json", DOMAIN))
    with (
        patch(
            "electrasmart.api.ElectraAPI.generate_new_token",
            return_value=mock_generate_token,
        ),
        patch(
            "electrasmart.api.ElectraAPI.validate_one_time_password",
            return_value=mock_otp_response,
        ),
        patch(
            "electrasmart.api.ElectraAPI.fetch_devices",
            return_value=[],
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567", CONF_OTP: "1234"},
        )

        # test with required
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_one_time_password_api_error(hass: HomeAssistant) -> None:
    """Test one time password."""
    mock_generate_token = loads(load_fixture("generate_token_response.json", DOMAIN))
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
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
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
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_phone_number(hass: HomeAssistant) -> None:
    """Test invalid phone number."""

    mock_invalid_phone_number_response = loads(
        load_fixture("invalid_phone_number_response.json", DOMAIN)
    )

    with patch(
        "electrasmart.api.ElectraAPI.generate_new_token",
        return_value=mock_invalid_phone_number_response,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "invalid_phone_number"}


async def test_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth."""

    mock_generate_token_response = loads(
        load_fixture("generate_token_response.json", DOMAIN)
    )
    mock_invalid_otp_response = loads(load_fixture("invalid_otp_response.json", DOMAIN))

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
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567", CONF_OTP: "1234"},
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP: "1234"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == CONF_OTP
    assert result["errors"] == {CONF_OTP: "invalid_auth"}
