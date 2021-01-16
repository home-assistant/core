"""Test the Cisco Webex config flow."""
import pytest
import requests

from homeassistant import config_entries, setup
from homeassistant.components.cisco_webex.config_flow import (
    CannotConnect,
    EmailNotFound,
    InvalidAuth,
    InvalidAuthTokenType,
    InvalidEmail,
    validate_config,
)
from homeassistant.components.cisco_webex.const import DOMAIN

from tests.async_mock import patch
from tests.components.cisco_webex.mocks import MockApiError, MockWebexTeamsAPI

TEST_DATA = {"email": "fff@fff.com"}

MOCK_API = MockWebexTeamsAPI(access_token="123")


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        return_value=True,
    ), patch(
        "homeassistant.components.cisco_webex.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.cisco_webex.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "unknown - test-email@test.com"
    assert result2["data"] == {
        "token": "asdasdas",
        "email": "test-email@test.com",
        "display_name": "unknown",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_validate_config_ok(hass):
    """Test validate_config method."""

    result = validate_config(MOCK_API, TEST_DATA)

    assert result is True


async def test_validate_config_not_bot_raises_invalid_token_type(hass):
    """Test validate_config raises InvalidAuthTokenType."""

    with patch(
        "tests.components.cisco_webex.mocks.MockPerson.type",
        return_value="person",
    ):
        with pytest.raises(InvalidAuthTokenType):
            validate_config(MOCK_API, TEST_DATA)


async def test_validate_config_raises_email_not_found_api_error(hass):
    """Test validate_config raises EmailNotFound."""

    exception_to_raise = MockApiError
    exception_to_raise.status_code = 400
    with patch(
        "tests.components.cisco_webex.mocks.MockPeopleAPI.me",
        side_effect=exception_to_raise,
    ):
        with pytest.raises(EmailNotFound):
            validate_config(MOCK_API, TEST_DATA)


async def test_validate_config_raises_email_not_found_person_none(hass):
    """Test validate_config raises EmailNotFound."""
    with patch(
        "tests.components.cisco_webex.mocks.MockPeopleAPI.list",
        return_value=[],
    ):
        with pytest.raises(EmailNotFound):
            validate_config(MOCK_API, TEST_DATA)


async def test_validate_config_raises_invalid_auth_api_error(hass):
    """Test validate_config raises InvalidAuth via Api error."""

    exception_to_raise = MockApiError
    exception_to_raise.status_code = 401
    with patch(
        "tests.components.cisco_webex.mocks.MockPeopleAPI.me",
        side_effect=exception_to_raise,
    ):
        with pytest.raises(InvalidAuth):
            validate_config(MOCK_API, TEST_DATA)


async def test_validate_config_raises_general_error(hass):
    """Test validate_config raises general error."""

    exception_to_raise = MockApiError
    exception_to_raise.status_code = 500
    with patch(
        "tests.components.cisco_webex.mocks.MockPeopleAPI.me",
        side_effect=exception_to_raise,
    ):
        with pytest.raises(exception_to_raise):
            validate_config(MOCK_API, TEST_DATA)


async def test_validate_config_raises_cannot_connect_error(hass):
    """Test validate_config raises cannot connect error."""

    exception_to_raise = MockApiError
    exception_to_raise.status_code = 500
    with patch(
        "tests.components.cisco_webex.mocks.MockPeopleAPI.me",
        side_effect=requests.exceptions.ConnectionError,
    ):
        with pytest.raises(CannotConnect):
            validate_config(MOCK_API, TEST_DATA)


async def test_form_invalid_email(hass):
    """Test form handles invalid email format."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=InvalidEmail,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_email"}


async def test_form_email_not_found(hass):
    """Test form handles email not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=EmailNotFound,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "email_not_found"}


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_general_exception(hass):
    """Test we handle an unknown exception."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "unknown"}


async def test_form_invalid_auth_token_type(hass):
    """Test we handle invalid auth token type."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=InvalidAuthTokenType,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth_token_type"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.cisco_webex.config_flow.validate_config",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"token": "asdasdas", "email": "test-email@test.com"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
