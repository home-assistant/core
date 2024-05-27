"""Tests for the Subaru component config flow."""

from copy import deepcopy
from unittest import mock
from unittest.mock import PropertyMock, patch

import pytest
from subarulink.exceptions import InvalidCredentials, InvalidPIN, SubaruException

from homeassistant import config_entries
from homeassistant.components.subaru import config_flow
from homeassistant.components.subaru.const import CONF_UPDATE_ENABLED, DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import (
    MOCK_API_2FA_CONTACTS,
    MOCK_API_2FA_REQUEST,
    MOCK_API_2FA_VERIFY,
    MOCK_API_CONNECT,
    MOCK_API_DEVICE_REGISTERED,
    MOCK_API_IS_PIN_REQUIRED,
    MOCK_API_TEST_PIN,
    MOCK_API_UPDATE_SAVED_PIN,
    TEST_CONFIG,
    TEST_CREDS,
    TEST_DEVICE_ID,
    TEST_PIN,
    TEST_USERNAME,
)

from tests.common import MockConfigEntry

ASYNC_SETUP_ENTRY = "homeassistant.components.subaru.async_setup_entry"
MOCK_2FA_CONTACTS = {
    "phone": "123-123-1234",
    "userName": "email@addr.com",
}


async def test_user_form_init(user_form) -> None:
    """Test the initial user form for first step of the config flow."""
    assert user_form["description_placeholders"] is None
    assert user_form["errors"] is None
    assert user_form["handler"] == DOMAIN
    assert user_form["step_id"] == "user"
    assert user_form["type"] is FlowResultType.FORM


async def test_user_form_repeat_identifier(hass: HomeAssistant, user_form) -> None:
    """Test we handle repeat identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN, title=TEST_USERNAME, data=TEST_CREDS, options=None
    )
    entry.add_to_hass(hass)

    with patch(
        MOCK_API_CONNECT,
        return_value=True,
    ) as mock_connect:
        result = await hass.config_entries.flow.async_configure(
            user_form["flow_id"],
            TEST_CREDS,
        )
    assert len(mock_connect.mock_calls) == 0
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_form_cannot_connect(hass: HomeAssistant, user_form) -> None:
    """Test we handle cannot connect error."""
    with patch(
        MOCK_API_CONNECT,
        side_effect=SubaruException(None),
    ) as mock_connect:
        result = await hass.config_entries.flow.async_configure(
            user_form["flow_id"],
            TEST_CREDS,
        )
    assert len(mock_connect.mock_calls) == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_user_form_invalid_auth(hass: HomeAssistant, user_form) -> None:
    """Test we handle invalid auth."""
    with patch(
        MOCK_API_CONNECT,
        side_effect=InvalidCredentials("invalidAccount"),
    ) as mock_connect:
        result = await hass.config_entries.flow.async_configure(
            user_form["flow_id"],
            TEST_CREDS,
        )
    assert len(mock_connect.mock_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_form_pin_not_required(
    hass: HomeAssistant, two_factor_verify_form
) -> None:
    """Test successful login when no PIN is required."""
    with (
        patch(
            MOCK_API_2FA_VERIFY,
            return_value=True,
        ) as mock_two_factor_verify,
        patch(
            MOCK_API_IS_PIN_REQUIRED,
            return_value=False,
        ) as mock_is_pin_required,
        patch(ASYNC_SETUP_ENTRY, return_value=True) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            two_factor_verify_form["flow_id"],
            user_input={config_flow.CONF_VALIDATION_CODE: "123456"},
        )
    assert len(mock_two_factor_verify.mock_calls) == 1
    assert len(mock_is_pin_required.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    expected = {
        "context": {"source": "user"},
        "title": TEST_USERNAME,
        "description": None,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "result": mock.ANY,
        "handler": DOMAIN,
        "type": "create_entry",
        "version": 1,
        "data": deepcopy(TEST_CONFIG),
        "options": {},
        "minor_version": 1,
    }

    expected["data"][CONF_PIN] = None
    result["data"][CONF_DEVICE_ID] = TEST_DEVICE_ID
    assert result == expected


async def test_registered_pin_required(hass: HomeAssistant, user_form) -> None:
    """Test if the device is already registered and PIN required."""
    with (
        patch(MOCK_API_CONNECT, return_value=True),
        patch(
            MOCK_API_DEVICE_REGISTERED, new_callable=PropertyMock
        ) as mock_device_registered,
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=True),
    ):
        mock_device_registered.return_value = True
        await hass.config_entries.flow.async_configure(
            user_form["flow_id"], user_input=TEST_CREDS
        )


async def test_registered_no_pin_required(hass: HomeAssistant, user_form) -> None:
    """Test if the device is already registered and PIN not required."""
    with (
        patch(MOCK_API_CONNECT, return_value=True),
        patch(
            MOCK_API_DEVICE_REGISTERED, new_callable=PropertyMock
        ) as mock_device_registered,
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=False),
    ):
        mock_device_registered.return_value = True
        await hass.config_entries.flow.async_configure(
            user_form["flow_id"], user_input=TEST_CREDS
        )


async def test_two_factor_request_success(
    hass: HomeAssistant, two_factor_start_form
) -> None:
    """Test two factor contact method selection."""
    with (
        patch(
            MOCK_API_2FA_REQUEST,
            return_value=True,
        ) as mock_two_factor_request,
        patch(MOCK_API_2FA_CONTACTS, new_callable=PropertyMock) as mock_contacts,
    ):
        mock_contacts.return_value = MOCK_2FA_CONTACTS
        await hass.config_entries.flow.async_configure(
            two_factor_start_form["flow_id"],
            user_input={config_flow.CONF_CONTACT_METHOD: "email@addr.com"},
        )
    assert len(mock_two_factor_request.mock_calls) == 1


async def test_two_factor_request_fail(
    hass: HomeAssistant, two_factor_start_form
) -> None:
    """Test two factor auth request failure."""
    with (
        patch(
            MOCK_API_2FA_REQUEST,
            return_value=False,
        ) as mock_two_factor_request,
        patch(MOCK_API_2FA_CONTACTS, new_callable=PropertyMock) as mock_contacts,
    ):
        mock_contacts.return_value = MOCK_2FA_CONTACTS
        result = await hass.config_entries.flow.async_configure(
            two_factor_start_form["flow_id"],
            user_input={config_flow.CONF_CONTACT_METHOD: "email@addr.com"},
        )
    assert len(mock_two_factor_request.mock_calls) == 1
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "two_factor_request_failed"


async def test_two_factor_verify_success(
    hass: HomeAssistant, two_factor_verify_form
) -> None:
    """Test two factor verification."""
    with (
        patch(
            MOCK_API_2FA_VERIFY,
            return_value=True,
        ) as mock_two_factor_verify,
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=True) as mock_is_in_required,
    ):
        await hass.config_entries.flow.async_configure(
            two_factor_verify_form["flow_id"],
            user_input={config_flow.CONF_VALIDATION_CODE: "123456"},
        )
    assert len(mock_two_factor_verify.mock_calls) == 1
    assert len(mock_is_in_required.mock_calls) == 1


async def test_two_factor_verify_bad_format(
    hass: HomeAssistant, two_factor_verify_form
) -> None:
    """Test two factor verification bad format."""
    with (
        patch(
            MOCK_API_2FA_VERIFY,
            return_value=False,
        ) as mock_two_factor_verify,
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=True) as mock_is_pin_required,
    ):
        result = await hass.config_entries.flow.async_configure(
            two_factor_verify_form["flow_id"],
            user_input={config_flow.CONF_VALIDATION_CODE: "1234567"},
        )
    assert len(mock_two_factor_verify.mock_calls) == 0
    assert len(mock_is_pin_required.mock_calls) == 0
    assert result["errors"] == {"base": "bad_validation_code_format"}


async def test_two_factor_verify_fail(
    hass: HomeAssistant, two_factor_verify_form
) -> None:
    """Test two factor verification failure."""
    with (
        patch(
            MOCK_API_2FA_VERIFY,
            return_value=False,
        ) as mock_two_factor_verify,
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=True) as mock_is_pin_required,
    ):
        result = await hass.config_entries.flow.async_configure(
            two_factor_verify_form["flow_id"],
            user_input={config_flow.CONF_VALIDATION_CODE: "123456"},
        )
    assert len(mock_two_factor_verify.mock_calls) == 1
    assert len(mock_is_pin_required.mock_calls) == 0
    assert result["errors"] == {"base": "incorrect_validation_code"}


async def test_pin_form_init(pin_form) -> None:
    """Test the pin entry form for second step of the config flow."""
    expected = {
        "data_schema": config_flow.PIN_SCHEMA,
        "description_placeholders": None,
        "errors": None,
        "flow_id": mock.ANY,
        "handler": DOMAIN,
        "step_id": "pin",
        "type": "form",
        "last_step": None,
        "preview": None,
    }
    assert pin_form == expected


async def test_pin_form_bad_pin_format(hass: HomeAssistant, pin_form) -> None:
    """Test we handle invalid pin."""
    with (
        patch(
            MOCK_API_TEST_PIN,
        ) as mock_test_pin,
        patch(
            MOCK_API_UPDATE_SAVED_PIN,
            return_value=True,
        ) as mock_update_saved_pin,
    ):
        result = await hass.config_entries.flow.async_configure(
            pin_form["flow_id"], user_input={CONF_PIN: "abcd"}
        )
    assert len(mock_test_pin.mock_calls) == 0
    assert len(mock_update_saved_pin.mock_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "bad_pin_format"}


async def test_pin_form_success(hass: HomeAssistant, pin_form) -> None:
    """Test successful PIN entry."""
    with (
        patch(
            MOCK_API_TEST_PIN,
            return_value=True,
        ) as mock_test_pin,
        patch(
            MOCK_API_UPDATE_SAVED_PIN,
            return_value=True,
        ) as mock_update_saved_pin,
        patch(ASYNC_SETUP_ENTRY, return_value=True) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            pin_form["flow_id"], user_input={CONF_PIN: TEST_PIN}
        )

    assert len(mock_test_pin.mock_calls) == 1
    assert len(mock_update_saved_pin.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    expected = {
        "context": {"source": "user"},
        "title": TEST_USERNAME,
        "description": None,
        "description_placeholders": None,
        "flow_id": mock.ANY,
        "result": mock.ANY,
        "handler": DOMAIN,
        "type": "create_entry",
        "version": 1,
        "data": TEST_CONFIG,
        "options": {},
        "minor_version": 1,
    }
    result["data"][CONF_DEVICE_ID] = TEST_DEVICE_ID
    assert result == expected


async def test_pin_form_incorrect_pin(hass: HomeAssistant, pin_form) -> None:
    """Test we handle invalid pin."""
    with (
        patch(
            MOCK_API_TEST_PIN,
            side_effect=InvalidPIN("invalidPin"),
        ) as mock_test_pin,
        patch(
            MOCK_API_UPDATE_SAVED_PIN,
            return_value=True,
        ) as mock_update_saved_pin,
    ):
        result = await hass.config_entries.flow.async_configure(
            pin_form["flow_id"], user_input={CONF_PIN: TEST_PIN}
        )
    assert len(mock_test_pin.mock_calls) == 1
    assert len(mock_update_saved_pin.mock_calls) == 1
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "incorrect_pin"}


async def test_option_flow_form(options_form) -> None:
    """Test config flow options form."""
    assert options_form["description_placeholders"] is None
    assert options_form["errors"] is None
    assert options_form["step_id"] == "init"
    assert options_form["type"] is FlowResultType.FORM


async def test_option_flow(hass: HomeAssistant, options_form) -> None:
    """Test config flow options."""
    result = await hass.config_entries.options.async_configure(
        options_form["flow_id"],
        user_input={
            CONF_UPDATE_ENABLED: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_UPDATE_ENABLED: False,
    }


@pytest.fixture
async def user_form(hass):
    """Return initial form for Subaru config flow."""
    return await hass.config_entries.flow.async_init(
        config_flow.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


@pytest.fixture
async def two_factor_start_form(hass, user_form):
    """Return two factor form for Subaru config flow."""
    with (
        patch(MOCK_API_CONNECT, return_value=True),
        patch(MOCK_API_2FA_CONTACTS, new_callable=PropertyMock) as mock_contacts,
    ):
        mock_contacts.return_value = MOCK_2FA_CONTACTS
        return await hass.config_entries.flow.async_configure(
            user_form["flow_id"], user_input=TEST_CREDS
        )


@pytest.fixture
async def two_factor_verify_form(hass, two_factor_start_form):
    """Return two factor form for Subaru config flow."""
    with (
        patch(
            MOCK_API_2FA_REQUEST,
            return_value=True,
        ),
        patch(MOCK_API_2FA_CONTACTS, new_callable=PropertyMock) as mock_contacts,
    ):
        mock_contacts.return_value = MOCK_2FA_CONTACTS
        return await hass.config_entries.flow.async_configure(
            two_factor_start_form["flow_id"],
            user_input={config_flow.CONF_CONTACT_METHOD: "email@addr.com"},
        )


@pytest.fixture
async def pin_form(hass, two_factor_verify_form):
    """Return PIN input form for Subaru config flow."""
    with (
        patch(
            MOCK_API_2FA_VERIFY,
            return_value=True,
        ),
        patch(MOCK_API_IS_PIN_REQUIRED, return_value=True),
    ):
        return await hass.config_entries.flow.async_configure(
            two_factor_verify_form["flow_id"],
            user_input={config_flow.CONF_VALIDATION_CODE: "123456"},
        )


@pytest.fixture
async def options_form(hass):
    """Return options form for Subaru config flow."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=None)
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {})
    return await hass.config_entries.options.async_init(entry.entry_id)
