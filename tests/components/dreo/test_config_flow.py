"""Test dreo config flow."""

from unittest.mock import MagicMock, patch

from pydreo.exceptions import DreoBusinessException, DreoException

from homeassistant.components.dreo.config_flow import DreoFlowHandler
from homeassistant.components.dreo.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test successful user step."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()

        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    expected_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "482c811da5d5b4bc6d497ffa98491e38",
    }
    assert result["data"] == expected_data


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step with connection error."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "password123"}

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoException("Connection error")

        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is not None
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test user step with invalid credentials."""
    flow = DreoFlowHandler()
    flow.hass = hass
    flow.context = {}

    user_input = {CONF_USERNAME: "test@example.com", CONF_PASSWORD: "wrongpassword"}

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoBusinessException("Invalid credentials")

        result = await flow.async_step_user(user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is not None
    assert result["errors"]["base"] == "invalid_auth"


async def test_user_step_unique_id_already_configured(hass: HomeAssistant) -> None:
    """Test user step when unique ID is already configured."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "existing@example.com",
            CONF_PASSWORD: "482c811da5d5b4bc6d497ffa98491e38",
        },
        unique_id="existing@example.com",
    )
    existing_entry.add_to_hass(hass)

    user_input = {CONF_USERNAME: "existing@example.com", CONF_PASSWORD: "password123"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data=user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(hass: HomeAssistant) -> None:
    """Test successful reauthentication flow."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "482c811da5d5b4bc6d497ffa98491e38",
        },
        unique_id="test@example.com",
    )
    existing_entry.add_to_hass(hass)

    result = await existing_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=True,
        ),
        patch(
            "homeassistant.components.dreo.config_flow.DreoClient"
        ) as mock_client_class,
    ):
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert existing_entry.data[CONF_PASSWORD] == "f1086f68460b65771de50a970cd1242d"


def test_password_hashing() -> None:
    """Test password hashing functionality."""
    test_cases = [
        ("test123", "cc03e747a6afbbcbf8be7668acfebee5"),
        ("password123", "482c811da5d5b4bc6d497ffa98491e38"),
        ("", "d41d8cd98f00b204e9800998ecf8427e"),
        ("special!@#$%", "da421a85e166675e00ee6a0df1010f70"),
    ]

    for password, expected_hash in test_cases:
        actual_hash = DreoFlowHandler._hash_password(password)
        assert actual_hash == expected_hash
        assert len(actual_hash) == 32


async def test_validate_login_success(hass: HomeAssistant) -> None:
    """Test successful login validation."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login = MagicMock()

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        mock_client_class.assert_called_once_with("test_user", "test_pass")
        assert is_valid is True
        assert error is None


async def test_validate_login_connection_error(hass: HomeAssistant) -> None:
    """Test login validation with connection error."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoException("Network error")

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        assert is_valid is False
        assert error == "cannot_connect"


async def test_validate_login_invalid_credentials(hass: HomeAssistant) -> None:
    """Test login validation with invalid credentials."""
    flow = DreoFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.dreo.config_flow.DreoClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.login.side_effect = DreoBusinessException("Invalid auth")

        is_valid, error = await flow._validate_login("test_user", "test_pass")

        assert is_valid is False
        assert error == "invalid_auth"
