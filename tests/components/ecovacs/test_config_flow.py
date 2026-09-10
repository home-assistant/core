"""Test Ecovacs config flow."""

from collections.abc import Callable
from dataclasses import dataclass, field
import ssl
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from deebot_client.authentication import create_rest_config
from deebot_client.exceptions import (
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
    InvalidVerificationCodeError,
    MqttError,
)
from deebot_client.mqtt_client import create_mqtt_config
import pytest

from homeassistant.components.ecovacs.const import (
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFICATION_CODE,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
    InstanceMode,
)
from homeassistant.config_entries import SOURCE_USER, ConfigFlowResult
from homeassistant.const import CONF_DEVICE_ID, CONF_MODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    CLOUD_DEVICE_ID,
    SELF_HOSTED_DEVICE_ID,
    STORED_ENTRY_DATA_CLOUD,
    STORED_ENTRY_DATA_SELF_HOSTED,
    VALID_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_SELF_HOSTED,
    VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
)

from tests.common import MockConfigEntry

_USER_STEP_SELF_HOSTED = {CONF_MODE: InstanceMode.SELF_HOSTED}


@dataclass
class _TestFnUserInput:
    auth: dict[str, Any]
    user: dict[str, Any] = field(default_factory=dict)


async def _test_user_flow(
    hass: HomeAssistant,
    user_input: _TestFnUserInput,
) -> ConfigFlowResult:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input.user,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input.auth,
    )


async def _test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> ConfigFlowResult:
    """Start a reauth flow and return the shown reauth confirmation form."""
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    return result


@pytest.mark.parametrize(
    ("test_fn_user_input", "entry_data"),
    [
        (
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
            STORED_ENTRY_DATA_CLOUD,
        ),
        (
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
            STORED_ENTRY_DATA_SELF_HOSTED,
        ),
    ],
    ids=["cloud", "self_hosted"],
)
@pytest.mark.usefixtures("mock_device_id")
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    test_fn_user_input: _TestFnUserInput,
    entry_data: dict[str, Any],
) -> None:
    """Test the user config flow."""
    result = await _test_user_flow(hass, test_fn_user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == entry_data[CONF_USERNAME]
    assert result["data"] == entry_data
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


def _cannot_connect_error(user_input: dict[str, Any]) -> dict[str, str]:
    field = "base"
    if CONF_OVERRIDE_MQTT_URL in user_input:
        field = CONF_OVERRIDE_MQTT_URL

    return {field: "cannot_connect"}


@pytest.mark.parametrize(
    ("side_effect_mqtt", "errors_mqtt"),
    [
        (MqttError, _cannot_connect_error),
        (InvalidAuthenticationError, lambda _: {"base": "invalid_auth"}),
        (Exception, lambda _: {"base": "unknown"}),
    ],
    ids=["cannot_connect", "invalid_auth", "unknown"],
)
@pytest.mark.parametrize(
    ("side_effect_rest", "reason_rest"),
    [
        (ClientError, "cannot_connect"),
        (InvalidAuthenticationError, "invalid_auth"),
        (Exception, "unknown"),
    ],
    ids=["cannot_connect", "invalid_auth", "unknown"],
)
@pytest.mark.parametrize(
    ("test_fn_user_input", "entry_data"),
    [
        (
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
            STORED_ENTRY_DATA_CLOUD,
        ),
        (
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
            VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT
            | {CONF_DEVICE_ID: SELF_HOSTED_DEVICE_ID},
        ),
    ],
    ids=["cloud", "self_hosted"],
)
@pytest.mark.usefixtures("mock_device_id")
async def test_user_flow_raise_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    side_effect_rest: Exception,
    reason_rest: str,
    side_effect_mqtt: Exception,
    errors_mqtt: Callable[[dict[str, Any]], dict[str, str]],
    test_fn_user_input: _TestFnUserInput,
    entry_data: dict[str, Any],
) -> None:
    """Test handling error on library calls."""
    user_input_auth = test_fn_user_input.auth

    # Authenticator raises error
    mock_authenticator_authenticate.side_effect = side_effect_rest
    result = await _test_user_flow(hass, test_fn_user_input)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": reason_rest}
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_not_called()
    mock_setup_entry.assert_not_called()

    mock_authenticator_authenticate.reset_mock(side_effect=True)

    # MQTT raises error
    mock_mqtt_client.verify_config.side_effect = side_effect_mqtt
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == errors_mqtt(user_input_auth)
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()
    mock_setup_entry.assert_not_called()

    mock_authenticator_authenticate.reset_mock(side_effect=True)
    mock_mqtt_client.verify_config.reset_mock(side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == entry_data[CONF_USERNAME]
    assert result["data"] == entry_data
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


async def test_user_flow_self_hosted_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
) -> None:
    """Test handling selfhosted errors and custom ssl context."""

    result = await _test_user_flow(
        hass,
        _TestFnUserInput(
            VALID_ENTRY_DATA_SELF_HOSTED
            | {
                CONF_OVERRIDE_REST_URL: "bla://localhost:8000",
                CONF_OVERRIDE_MQTT_URL: "mqtt://",
            },
            _USER_STEP_SELF_HOSTED,
        ),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {
        CONF_OVERRIDE_REST_URL: "invalid_url_schema_override_rest_url",
        CONF_OVERRIDE_MQTT_URL: "invalid_url",
    }
    mock_authenticator_authenticate.assert_not_called()
    mock_mqtt_client.verify_config.assert_not_called()
    mock_setup_entry.assert_not_called()

    # Check that the schema includes select box to disable ssl verification of mqtt
    assert result["data_schema"] is not None
    assert CONF_VERIFY_MQTT_CERTIFICATE in result["data_schema"].schema

    data = VALID_ENTRY_DATA_SELF_HOSTED | {CONF_VERIFY_MQTT_CERTIFICATE: False}
    with patch(
        "homeassistant.components.ecovacs.config_flow.create_mqtt_config",
        wraps=create_mqtt_config,
    ) as mock_create_mqtt_config:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=data,
        )
        mock_create_mqtt_config.assert_called_once()
        ssl_context = mock_create_mqtt_config.call_args[1]["ssl_context"]
        assert isinstance(ssl_context, ssl.SSLContext)
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert ssl_context.check_hostname is False

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == data[CONF_USERNAME]
    assert result["data"] == data | {CONF_DEVICE_ID: SELF_HOSTED_DEVICE_ID}
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


@pytest.mark.parametrize(
    ("test_fn_user_input"),
    [
        _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
        _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
    ],
    ids=["cloud", "self_hosted"],
)
async def test_already_exists(
    hass: HomeAssistant,
    test_fn_user_input: _TestFnUserInput,
) -> None:
    """Test we don't allow duplicated config entries."""
    MockConfigEntry(domain=DOMAIN, data=test_fn_user_input.auth).add_to_hass(hass)

    result = await _test_user_flow(
        hass,
        test_fn_user_input,
    )

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("test_fn_user_input", "entry_data"),
    [
        (
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
            STORED_ENTRY_DATA_CLOUD,
        ),
        (
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
            STORED_ENTRY_DATA_SELF_HOSTED,
        ),
    ],
    ids=["cloud", "self_hosted"],
)
@pytest.mark.usefixtures("mock_device_id")
async def test_device_verification(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
    test_fn_user_input: _TestFnUserInput,
    entry_data: dict[str, Any],
) -> None:
    """Test verifying the Ecovacs client device ID during the user flow."""
    mock_authenticator.authenticate.side_effect = DeviceVerificationRequiredError

    result = await _test_user_flow(hass, test_fn_user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_verification"
    mock_authenticator.request_device_verification_code.assert_awaited_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "123456"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == entry_data
    mock_authenticator.verify_device.assert_awaited_once_with("123456")
    mock_authenticator.teardown.assert_awaited_once()
    mock_mqtt_client.verify_config.assert_called_once()
    mock_setup_entry.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(ClientError, {"base": "cannot_connect"}, id="cannot_connect"),
        pytest.param(Exception, {"base": "unknown"}, id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_device_id")
async def test_request_device_verification_code_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
    side_effect: type[Exception],
    errors: dict[str, str],
) -> None:
    """Test handling errors while requesting a device verification code."""
    mock_authenticator.authenticate.side_effect = DeviceVerificationRequiredError
    mock_authenticator.request_device_verification_code.side_effect = side_effect

    result = await _test_user_flow(hass, _TestFnUserInput(VALID_ENTRY_DATA_CLOUD))

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == errors
    mock_authenticator.verify_device.assert_not_called()
    mock_mqtt_client.verify_config.assert_not_called()
    mock_setup_entry.assert_not_called()


@pytest.mark.parametrize(
    ("side_effect", "errors"),
    [
        pytest.param(
            InvalidVerificationCodeError,
            {"base": "invalid_verification_code"},
            id="invalid_verification_code",
        ),
        pytest.param(ClientError, {"base": "cannot_connect"}, id="cannot_connect"),
        pytest.param(Exception, {"base": "unknown"}, id="unknown"),
    ],
)
@pytest.mark.usefixtures("mock_device_id")
async def test_verify_device_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
    side_effect: type[Exception],
    errors: dict[str, str],
) -> None:
    """Test handling errors while verifying the Ecovacs client device ID."""
    mock_authenticator.authenticate.side_effect = DeviceVerificationRequiredError

    result = await _test_user_flow(hass, _TestFnUserInput(VALID_ENTRY_DATA_CLOUD))
    mock_authenticator.verify_device.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "expired"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_verification"
    assert result["errors"] == errors
    mock_mqtt_client.verify_config.assert_not_called()
    mock_setup_entry.assert_not_called()


async def test_mqtt_retry_after_device_verification(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
) -> None:
    """Test retrying connection validation without reusing the email code."""
    mock_authenticator.authenticate.side_effect = [
        DeviceVerificationRequiredError,
        None,
    ]
    mock_mqtt_client.verify_config.side_effect = [MqttError, None]

    with patch(
        "homeassistant.components.ecovacs.config_flow.create_rest_config",
        wraps=create_rest_config,
    ) as mock_create_rest_config:
        result = await _test_user_flow(hass, _TestFnUserInput(VALID_ENTRY_DATA_CLOUD))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_VERIFICATION_CODE: "123456"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "auth"
        assert result["errors"] == {"base": "cannot_connect"}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=VALID_ENTRY_DATA_CLOUD
        )
        await hass.async_block_till_done()

    # The verified device ID is reused, so no new verification code is required
    assert mock_create_rest_config.call_count == 2
    device_id = mock_create_rest_config.call_args_list[0].kwargs["device_id"]
    assert mock_create_rest_config.call_args_list[1].kwargs["device_id"] == device_id

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == VALID_ENTRY_DATA_CLOUD | {CONF_DEVICE_ID: device_id}
    mock_authenticator.request_device_verification_code.assert_awaited_once()
    mock_authenticator.verify_device.assert_awaited_once_with("123456")
    # The superseded authenticator and the one of the created entry are torn down
    assert mock_authenticator.teardown.await_count == 2
    assert mock_mqtt_client.verify_config.call_count == 2
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_mqtt_client")
async def test_reauth(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
) -> None:
    """Test reauthentication without a required device verification."""
    result = await _test_reauth_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "new-password"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # The already verified device ID is kept, so no new verification is required
    assert mock_config_entry.data == STORED_ENTRY_DATA_CLOUD | {
        CONF_PASSWORD: "new-password"
    }
    mock_authenticator.request_device_verification_code.assert_not_called()
    mock_authenticator.verify_device.assert_not_called()
    mock_setup_entry.assert_called_once()


@pytest.mark.usefixtures("mock_mqtt_client")
async def test_reauth_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
) -> None:
    """Test handling invalid credentials during reauthentication."""
    mock_authenticator.authenticate.side_effect = InvalidAuthenticationError

    result = await _test_reauth_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "wrong-password"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
    assert mock_config_entry.data == STORED_ENTRY_DATA_CLOUD
    mock_setup_entry.assert_not_called()


async def test_reauth_device_verification(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
) -> None:
    """Test device verification for an existing config entry."""
    mock_authenticator.authenticate.side_effect = DeviceVerificationRequiredError

    result = await _test_reauth_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: VALID_ENTRY_DATA_CLOUD[CONF_PASSWORD]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "device_verification"
    mock_authenticator.request_device_verification_code.assert_awaited_once()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_DEVICE_ID] == CLOUD_DEVICE_ID
    mock_authenticator.verify_device.assert_awaited_once_with("123456")
    mock_mqtt_client.verify_config.assert_called_once()
    mock_setup_entry.assert_called_once()


async def test_reauth_mqtt_retry_after_device_verification(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
    mock_mqtt_client: Mock,
) -> None:
    """Test retrying a reauthentication without reusing the email code."""
    mock_authenticator.authenticate.side_effect = [
        DeviceVerificationRequiredError,
        None,
    ]
    mock_mqtt_client.verify_config.side_effect = [MqttError, None]

    result = await _test_reauth_flow(hass, mock_config_entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: VALID_ENTRY_DATA_CLOUD[CONF_PASSWORD]},
    )
    assert result["step_id"] == "device_verification"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_VERIFICATION_CODE: "123456"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "cannot_connect"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_PASSWORD: VALID_ENTRY_DATA_CLOUD[CONF_PASSWORD]},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_DEVICE_ID] == CLOUD_DEVICE_ID
    # The verified device ID is reused, so no new verification code is required
    mock_authenticator.request_device_verification_code.assert_awaited_once()
    mock_authenticator.verify_device.assert_awaited_once_with("123456")
    assert mock_mqtt_client.verify_config.call_count == 2
    mock_setup_entry.assert_called_once()
