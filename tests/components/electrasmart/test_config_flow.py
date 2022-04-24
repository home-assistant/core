"""Test the Electra Smart config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.electrasmart.config_flow import ElectraApiError
from homeassistant.components.electrasmart.const import (
    CONF_OTP,
    CONF_PHONE_NUMBER,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM

from tests.components.electrasmart.test_data import (
    MOCK_DATA_GENERATE_TOKEN_RESP,
    MOCK_DATA_INVALID_OTP,
    MOCK_DATA_INVALID_PHONE_NUMBER,
    MOCK_DATA_OTP_RESP,
)

# from .test_data import (
#     MOCK_FAILED_TO_LOGIN_MSG,
#     MOCK_GET_CONFIGURATION,
#     MOCK_INVALID_TOKEN_MGS,
# )


async def test_user(hass: HomeAssistant):
    """Test user config."""

    with patch(
        "electra.ElectraAPI.generate_new_token",
        return_value=MOCK_DATA_GENERATE_TOKEN_RESP,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == CONF_OTP


async def test_one_time_password(hass: HomeAssistant):
    """Test one time password."""
    with patch(
        "electra.ElectraAPI.generate_new_token",
        return_value=MOCK_DATA_GENERATE_TOKEN_RESP,
    ), patch(
        "electra.ElectraAPI.validate_one_time_password", return_value=MOCK_DATA_OTP_RESP
    ), patch(
        "electra.ElectraAPI.get_devices", return_value=[]
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
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


async def test_cannot_connect(hass: HomeAssistant):
    """Test cannot connect."""

    with patch(
        "electra.ElectraAPI.generate_new_token",
        side_effect=ElectraApiError,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_phone_number(hass: HomeAssistant):
    """Test invalid phone number."""

    with patch(
        "electra.ElectraAPI.generate_new_token",
        return_value=MOCK_DATA_INVALID_PHONE_NUMBER,
    ):
        # test with required
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_PHONE_NUMBER: "0521234567"},
        )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"phone_number": "invalid_phone_number"}


async def test_invalid_auth(hass: HomeAssistant):
    """Test invalid auth."""

    with patch(
        "electra.ElectraAPI.generate_new_token",
        return_value=MOCK_DATA_GENERATE_TOKEN_RESP,
    ), patch(
        "electra.ElectraAPI.validate_one_time_password",
        return_value=MOCK_DATA_INVALID_OTP,
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
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == CONF_OTP
    assert result["errors"] == {CONF_OTP: "invalid_auth"}
