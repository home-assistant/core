"""Test the Picnic config flow."""

from unittest.mock import patch

import pytest
from python_picnic_api2.session import (
    Picnic2FAError,
    Picnic2FARequired,
    PicnicAuthError,
)
import requests

from homeassistant import config_entries
from homeassistant.components.picnic.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_COUNTRY_CODE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def picnic_api():
    """Create PicnicAPI mock with set response data."""
    auth_token = "af3wh738j3fa28l9fa23lhiufahu7l"
    auth_data = {
        "user_id": "f29-2a6-o32n",
        "address": {
            "street": "Teststreet",
            "house_number": 123,
            "house_number_ext": "b",
        },
    }
    with patch(
        "homeassistant.components.picnic.config_flow.PicnicAPI",
    ) as picnic_mock:
        instance = picnic_mock.return_value
        instance.session.auth_token = auth_token
        instance.get_user.return_value = auth_data
        instance.login.return_value = None  # no 2FA by default
        instance.generate_2fa_code.return_value = None
        instance.verify_2fa_code.return_value = None

        yield picnic_mock


async def test_form(hass: HomeAssistant, picnic_api) -> None:
    """Test we get the form and a config entry is created."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Picnic"
    assert result2["data"] == {
        CONF_ACCESS_TOKEN: picnic_api().session.auth_token,
        CONF_COUNTRY_CODE: "NL",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_2fa_required(hass: HomeAssistant, picnic_api) -> None:
    """Test the full 2FA flow."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        assert result_step_2fa_channel["type"] is FlowResultType.FORM
        assert result_step_2fa_channel["step_id"] == "2fa"

        result_step_2fa_verify = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_code": "123456"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_verify["type"] is FlowResultType.CREATE_ENTRY
    assert result_step_2fa_verify["title"] == "Picnic"
    assert result_step_2fa_verify["data"] == {
        CONF_ACCESS_TOKEN: picnic_api().session.auth_token,
        CONF_COUNTRY_CODE: "NL",
    }
    assert picnic_api.return_value.generate_2fa_code.call_count == 1
    assert picnic_api.return_value.generate_2fa_code.call_args[0] == ("SMS",)
    assert picnic_api.return_value.verify_2fa_code.call_count == 1
    assert picnic_api.return_value.verify_2fa_code.call_args[0] == ("123456",)


async def test_form_2fa_channel_cannot_connect(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle connection errors in the first 2fa step."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired
    picnic_api.return_value.generate_2fa_code.side_effect = (
        requests.exceptions.ConnectionError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_channel["type"] is FlowResultType.FORM
    assert result_step_2fa_channel["errors"] == {"base": "cannot_connect"}


async def test_form_2fa_channel_exception(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle random exceptions in the first 2fa step."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired
    picnic_api.return_value.generate_2fa_code.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_channel["type"] is FlowResultType.FORM
    assert result_step_2fa_channel["errors"] == {"base": "unknown"}


async def test_form_2fa_wrong_code(hass: HomeAssistant, picnic_api) -> None:
    """Test the full 2FA flow with incorrect code."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired
    picnic_api.return_value.verify_2fa_code.side_effect = Picnic2FAError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        assert result_step_2fa_channel["type"] is FlowResultType.FORM
        assert result_step_2fa_channel["step_id"] == "2fa"

        result_step_2fa_verify = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_code": "654321"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_verify["type"] is FlowResultType.FORM
    assert result_step_2fa_verify["errors"] == {"base": "invalid_2fa_code"}


async def test_form_2fa_cannot_connect(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle connection errors in the last 2fa step."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired
    picnic_api.return_value.verify_2fa_code.side_effect = (
        requests.exceptions.ConnectionError
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        assert result_step_2fa_channel["type"] is FlowResultType.FORM
        assert result_step_2fa_channel["step_id"] == "2fa"

        result_step_2fa_verify = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_code": "123456"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_verify["type"] is FlowResultType.FORM
    assert result_step_2fa_verify["errors"] == {"base": "cannot_connect"}


async def test_form_2fa_exception(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle random exceptions in the last 2fa step."""
    picnic_api.return_value.login.side_effect = Picnic2FARequired
    picnic_api.return_value.verify_2fa_code.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_step_user = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        assert result_step_user["type"] is FlowResultType.FORM
        assert result_step_user["step_id"] == "2fa_channel"

        result_step_2fa_channel = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_channel": "sms"},
        )
        assert result_step_2fa_channel["type"] is FlowResultType.FORM
        assert result_step_2fa_channel["step_id"] == "2fa"

        result_step_2fa_verify = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"two_fa_code": "123456"},
        )
        await hass.async_block_till_done()

    assert result_step_2fa_verify["type"] is FlowResultType.FORM
    assert result_step_2fa_verify["errors"] == {"base": "unknown"}


async def test_form_invalid_auth(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle invalid authentication."""
    picnic_api.return_value.login.side_effect = PicnicAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "country_code": "NL",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle connection errors."""
    picnic_api.return_value.login.side_effect = requests.exceptions.ConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "country_code": "NL",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_exception(hass: HomeAssistant, picnic_api) -> None:
    """Test we handle random exceptions."""
    picnic_api.return_value.login.side_effect = Exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "country_code": "NL",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_form_already_configured(hass: HomeAssistant, picnic_api) -> None:
    """Test that an entry with unique id can only be added once."""
    # Create a mocked config entry and make sure to use the same user_id as set for the picnic_api mock response.
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=picnic_api().get_user()["user_id"],
        data={CONF_ACCESS_TOKEN: "a3p98fsen.a39p3fap", CONF_COUNTRY_CODE: "NL"},
    ).add_to_hass(hass)

    result_init = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "country_code": "NL",
        },
    )
    await hass.async_block_till_done()

    assert result_configure["type"] is FlowResultType.ABORT
    assert result_configure["reason"] == "already_configured"


async def test_step_reauth(hass: HomeAssistant, picnic_api) -> None:
    """Test the re-auth flow."""
    # Create a mocked config entry
    conf = {CONF_ACCESS_TOKEN: "a3p98fsen.a39p3fap", CONF_COUNTRY_CODE: "NL"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=picnic_api().get_user()["user_id"],
        data=conf,
    )
    entry.add_to_hass(hass)

    # Init a re-auth flow
    result_init = await entry.start_reauth_flow(hass)
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "user"

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        await hass.async_block_till_done()

    # Check that the returned flow has type abort because of successful re-authentication
    assert result_configure["type"] is FlowResultType.ABORT
    assert result_configure["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1


async def test_step_reauth_failed(hass: HomeAssistant, picnic_api) -> None:
    """Test the re-auth flow when authentication fails."""
    picnic_api.return_value.login.side_effect = PicnicAuthError

    # Create a mocked config entry
    user_id = "f29-2a6-o32n"
    conf = {CONF_ACCESS_TOKEN: "a3p98fsen.a39p3fap", CONF_COUNTRY_CODE: "NL"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=user_id,
        data=conf,
    )
    entry.add_to_hass(hass)

    # Init a re-auth flow
    result_init = await entry.start_reauth_flow(hass)
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "user"

    result_configure = await hass.config_entries.flow.async_configure(
        result_init["flow_id"],
        {
            "username": "test-username",
            "password": "test-password",
            "country_code": "NL",
        },
    )
    await hass.async_block_till_done()

    # Check that the returned flow has type form with error set
    assert result_configure["type"] is FlowResultType.FORM
    assert result_configure["errors"] == {"base": "invalid_auth"}

    assert len(hass.config_entries.async_entries()) == 1


async def test_step_reauth_different_account(hass: HomeAssistant, picnic_api) -> None:
    """Test the re-auth flow when authentication is done with a different account."""
    # Create a mocked config entry, unique_id should be different that the user id in the api response
    conf = {CONF_ACCESS_TOKEN: "a3p98fsen.a39p3fap", CONF_COUNTRY_CODE: "NL"}

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="3fpawh-ues-af3ho",
        data=conf,
    )
    entry.add_to_hass(hass)

    # Init a re-auth flow
    result_init = await entry.start_reauth_flow(hass)
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "user"

    with patch(
        "homeassistant.components.picnic.async_setup_entry",
        return_value=True,
    ):
        result_configure = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            {
                "username": "test-username",
                "password": "test-password",
                "country_code": "NL",
            },
        )
        await hass.async_block_till_done()

    # Check that the returned flow has type form with error set
    assert result_configure["type"] is FlowResultType.FORM
    assert result_configure["errors"] == {"base": "different_account"}

    assert len(hass.config_entries.async_entries()) == 1
