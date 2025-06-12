"""Tests for the Dreo config flow."""

from unittest.mock import patch

from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException
import pytest

from homeassistant.components.dreo.config_flow import DreoFlowHandler
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.skip(reason="Translation issue with data_description keys")
async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        "dreo", context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_async_step_user_success_integration(hass: HomeAssistant) -> None:
    """Test successful user step using integration test setup."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with patch.object(flow, "_validate_login", return_value=(True, None)):
        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    expected_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "482c811da5d5b4bc6d497ffa98491e38",
    }
    assert result["data"] == expected_data


async def test_async_step_user_invalid_credentials(hass: HomeAssistant) -> None:
    """Test user step with invalid credentials."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrongpassword"}

    with patch.object(flow, "_validate_login", return_value=(False, "cannot_connect")):
        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is not None
    assert result["errors"]["base"] == "cannot_connect"


async def test_async_step_user_business_exception(hass: HomeAssistant) -> None:
    """Test user step with business exception."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with patch.object(
        flow,
        "_validate_login",
        return_value=(False, "invalid_auth"),
    ):
        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is not None
    assert result["errors"]["base"] == "invalid_auth"


def test_hash_password() -> None:
    """Test password hashing."""
    password = "test123"
    hashed = DreoFlowHandler._hash_password(password)

    assert hashed != password
    assert len(hashed) == 32
    assert hashed == "cc03e747a6afbbcbf8be7668acfebee5"


def test_hash_password_unit() -> None:
    """Unit test for hash password function."""
    password = "password123"
    expected_hash = "482c811da5d5b4bc6d497ffa98491e38"

    actual_hash = DreoFlowHandler._hash_password(password)

    assert actual_hash == expected_hash


@pytest.fixture(autouse=True)
def mock_config_entries_setup():
    """Disable setting up entries for config flow tests."""
    with patch("homeassistant.config_entries.ConfigEntries.async_setup"):
        yield


async def test_validate_login_success(hass: HomeAssistant) -> None:
    """Test the _validate_login method with successful validation."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login = lambda: None

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        mock_client.assert_called_once_with("test_user", "test_pass")

        assert is_valid is True
        assert error is None


async def test_validate_login_cannot_connect(hass: HomeAssistant) -> None:
    """Test the _validate_login method with connection error."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login.side_effect = HsCloudException(
            "Connection error"
        )

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        assert is_valid is False
        assert error == "cannot_connect"


async def test_validate_login_invalid_auth(hass: HomeAssistant) -> None:
    """Test the _validate_login method with authentication error."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login.side_effect = HsCloudBusinessException(
            "Invalid auth"
        )

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        assert is_valid is False
        assert error == "invalid_auth"


async def test_validate_login_unit_success(hass: HomeAssistant) -> None:
    """Unit test for validate login success."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login = lambda: None

        result = await flow._validate_login("user", "pass")
        assert result == (True, None)


async def test_validate_login_unit_connection_error(hass: HomeAssistant) -> None:
    """Unit test for validate login connection error."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login.side_effect = HsCloudException("error")

        result = await flow._validate_login("user", "pass")
        assert result == (False, "cannot_connect")


async def test_validate_login_unit_auth_error(hass: HomeAssistant) -> None:
    """Unit test for validate login auth error."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch("homeassistant.components.dreo.config_flow.HsCloud") as mock_client:
        mock_client.return_value.login.side_effect = HsCloudBusinessException("error")

        result = await flow._validate_login("user", "pass")
        assert result == (False, "invalid_auth")


async def test_async_step_user_no_input_unit(hass: HomeAssistant) -> None:
    """Unit test for async_step_user with no input."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    result = await flow.async_step_user(None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_async_step_user_success_unit(hass: HomeAssistant) -> None:
    """Unit test for async_step_user with successful login."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with (
        patch.object(flow, "async_set_unique_id") as mock_set_id,
        patch.object(flow, "_abort_if_unique_id_configured") as mock_abort,
        patch.object(
            flow, "_validate_login", return_value=(True, None)
        ) as mock_validate,
        patch.object(flow, "async_create_entry") as mock_create,
    ):
        mock_create.return_value = {
            "type": FlowResultType.CREATE_ENTRY,
            "title": "test@example.com",
            "data": {
                CONF_USERNAME: "test@example.com",
                CONF_PASSWORD: "hashed_password",
            },
        }

        await flow.async_step_user(user_input)

        mock_set_id.assert_called_once_with("test@example.com")
        mock_abort.assert_called_once()

        mock_validate.assert_called_once()
        call_args = mock_validate.call_args[0]
        assert call_args[0] == "test@example.com"
        assert len(call_args[1]) == 32

        mock_create.assert_called_once()
        create_args = mock_create.call_args
        assert create_args[1]["title"] == "test@example.com"
        assert create_args[1]["data"][CONF_USERNAME] == "test@example.com"


async def test_async_step_user_login_failure_unit(hass: HomeAssistant) -> None:
    """Unit test for async_step_user with login failure."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrong_password"}

    with (
        patch.object(flow, "async_set_unique_id") as mock_set_id,
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_validate_login", return_value=(False, "invalid_auth")),
        patch.object(flow, "async_show_form") as mock_show_form,
    ):
        mock_show_form.return_value = {
            "type": FlowResultType.FORM,
            "step_id": "user",
            "errors": {"base": "invalid_auth"},
        }

        await flow.async_step_user(user_input)

        mock_set_id.assert_called_once_with("test@example.com")

        mock_show_form.assert_called_once()
        call_args = mock_show_form.call_args[1]
        assert call_args["errors"] == {"base": "invalid_auth"}


async def test_async_step_user_unknown_error_unit(hass: HomeAssistant) -> None:
    """Unit test for async_step_user with unknown error (None)."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with (
        patch.object(flow, "async_set_unique_id"),
        patch.object(flow, "_abort_if_unique_id_configured"),
        patch.object(flow, "_validate_login", return_value=(False, None)),
        patch.object(flow, "async_show_form") as mock_show_form,
    ):
        mock_show_form.return_value = {
            "type": FlowResultType.FORM,
            "step_id": "user",
            "errors": {"base": "unknown_error"},
        }

        await flow.async_step_user(user_input)

        mock_show_form.assert_called_once()
        call_args = mock_show_form.call_args[1]
        assert call_args["errors"] == {"base": "unknown_error"}
