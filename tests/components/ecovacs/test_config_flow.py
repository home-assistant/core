"""Test Ecovacs config flow."""

from collections.abc import Awaitable, Callable
import ssl
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError
from deebot_client.exceptions import InvalidAuthenticationError, MqttError
from deebot_client.mqtt_client import create_mqtt_config
import pytest

from homeassistant.components.ecovacs.const import (
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
    InstanceMode,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MODE, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
    VALID_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_SELF_HOSTED,
    VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
)

_USER_STEP_SELF_HOSTED = {CONF_MODE: InstanceMode.SELF_HOSTED}

_TEST_FN_AUTH_ARG = "user_input_auth"
_TEST_FN_USER_ARG = "user_input_user"


async def _test_user_flow(
    hass: HomeAssistant,
    user_input_auth: dict[str, Any],
) -> dict[str, Any]:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )


async def _test_user_flow_show_advanced_options(
    hass: HomeAssistant,
    *,
    user_input_auth: dict[str, Any],
    user_input_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Test config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER, "show_advanced_options": True},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_user or {},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input_auth,
    )


@pytest.mark.parametrize(
    ("test_fn", "test_fn_args", "entry_data"),
    [
        (
            _test_user_flow_show_advanced_options,
            {_TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_CLOUD},
            VALID_ENTRY_DATA_CLOUD,
        ),
        (
            _test_user_flow_show_advanced_options,
            {
                _TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_SELF_HOSTED,
                _TEST_FN_USER_ARG: _USER_STEP_SELF_HOSTED,
            },
            VALID_ENTRY_DATA_SELF_HOSTED,
        ),
        (
            _test_user_flow,
            {_TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_CLOUD},
            VALID_ENTRY_DATA_CLOUD,
        ),
    ],
    ids=["advanced_cloud", "advanced_self_hosted", "cloud"],
)
async def test_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    test_fn: Callable[[HomeAssistant, dict[str, Any]], Awaitable[dict[str, Any]]]
    | Callable[
        [HomeAssistant, dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]
    ],
    test_fn_args: dict[str, Any],
    entry_data: dict[str, Any],
) -> None:
    """Test the user config flow."""
    result = await test_fn(
        hass,
        **test_fn_args,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == entry_data[CONF_USERNAME]
    assert result["data"] == entry_data
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()


def _cannot_connect_error(user_input: dict[str, Any]) -> str:
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
    ("test_fn", "test_fn_args", "entry_data"),
    [
        (
            _test_user_flow_show_advanced_options,
            {_TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_CLOUD},
            VALID_ENTRY_DATA_CLOUD,
        ),
        (
            _test_user_flow_show_advanced_options,
            {
                _TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_SELF_HOSTED,
                _TEST_FN_USER_ARG: _USER_STEP_SELF_HOSTED,
            },
            VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
        ),
        (
            _test_user_flow,
            {_TEST_FN_AUTH_ARG: VALID_ENTRY_DATA_CLOUD},
            VALID_ENTRY_DATA_CLOUD,
        ),
    ],
    ids=["advanced_cloud", "advanced_self_hosted", "cloud"],
)
async def test_user_flow_raise_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_authenticator_authenticate: AsyncMock,
    mock_mqtt_client: Mock,
    side_effect_rest: Exception,
    reason_rest: str,
    side_effect_mqtt: Exception,
    errors_mqtt: Callable[[dict[str, Any]], str],
    test_fn: Callable[[HomeAssistant, dict[str, Any]], Awaitable[dict[str, Any]]]
    | Callable[
        [HomeAssistant, dict[str, Any], dict[str, Any]], Awaitable[dict[str, Any]]
    ],
    test_fn_args: dict[str, Any],
    entry_data: dict[str, Any],
) -> None:
    """Test handling error on library calls."""
    user_input_auth = test_fn_args[_TEST_FN_AUTH_ARG]

    # Authenticator raises error
    mock_authenticator_authenticate.side_effect = side_effect_rest
    result = await test_fn(
        hass,
        **test_fn_args,
    )
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

    result = await _test_user_flow_show_advanced_options(
        hass,
        user_input_auth=VALID_ENTRY_DATA_SELF_HOSTED
        | {
            CONF_OVERRIDE_REST_URL: "bla://localhost:8000",
            CONF_OVERRIDE_MQTT_URL: "mqtt://",
        },
        user_input_user=_USER_STEP_SELF_HOSTED,
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
    assert result["data"] == data
    mock_setup_entry.assert_called()
    mock_authenticator_authenticate.assert_called()
    mock_mqtt_client.verify_config.assert_called()
