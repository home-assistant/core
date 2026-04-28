"""Test Ecovacs config flow."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
import ssl
from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from aiohttp import ClientError
from deebot_client.exceptions import InvalidAuthenticationError, MqttError
from deebot_client.mqtt_client import create_mqtt_config
import pytest

from homeassistant.components.ecovacs.config_flow import (
    EcovacsOptionsFlowHandler,
    _device_pin_field_key,
)
from homeassistant.components.ecovacs.const import (
    CONF_CAMERA_PINS,
    CONF_OVERRIDE_MQTT_URL,
    CONF_OVERRIDE_REST_URL,
    CONF_VERIFY_MQTT_CERTIFICATE,
    DOMAIN,
    InstanceMode,
)
from deebot_client.camera.api import encode_pin
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_MODE, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import (
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
        user_input=user_input.auth,
    )


async def _test_user_flow_show_advanced_options(
    hass: HomeAssistant,
    user_input: _TestFnUserInput,
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
        user_input=user_input.user,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=user_input.auth,
    )


@pytest.mark.parametrize(
    ("test_fn", "test_fn_user_input", "entry_data"),
    [
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
            VALID_ENTRY_DATA_CLOUD,
        ),
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
            VALID_ENTRY_DATA_SELF_HOSTED,
        ),
        (
            _test_user_flow,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
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
    test_fn: Callable[[HomeAssistant, _TestFnUserInput], Awaitable[dict[str, Any]]],
    test_fn_user_input: _TestFnUserInput,
    entry_data: dict[str, Any],
) -> None:
    """Test the user config flow."""
    result = await test_fn(hass, test_fn_user_input)
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
    ("test_fn", "test_fn_user_input", "entry_data"),
    [
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
            VALID_ENTRY_DATA_CLOUD,
        ),
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
            VALID_ENTRY_DATA_SELF_HOSTED_WITH_VALIDATE_CERT,
        ),
        (
            _test_user_flow,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
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
    test_fn: Callable[[HomeAssistant, _TestFnUserInput], Awaitable[dict[str, Any]]],
    test_fn_user_input: _TestFnUserInput,
    entry_data: dict[str, Any],
) -> None:
    """Test handling error on library calls."""
    user_input_auth = test_fn_user_input.auth

    # Authenticator raises error
    mock_authenticator_authenticate.side_effect = side_effect_rest
    result = await test_fn(hass, test_fn_user_input)
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


@pytest.mark.parametrize(
    ("test_fn", "test_fn_user_input"),
    [
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
        ),
        (
            _test_user_flow_show_advanced_options,
            _TestFnUserInput(VALID_ENTRY_DATA_SELF_HOSTED, _USER_STEP_SELF_HOSTED),
        ),
        (
            _test_user_flow,
            _TestFnUserInput(VALID_ENTRY_DATA_CLOUD),
        ),
    ],
    ids=["advanced_cloud", "advanced_self_hosted", "cloud"],
)
async def test_already_exists(
    hass: HomeAssistant,
    test_fn: Callable[[HomeAssistant, _TestFnUserInput], Awaitable[dict[str, Any]]],
    test_fn_user_input: _TestFnUserInput,
) -> None:
    """Test we don't allow duplicated config entries."""
    MockConfigEntry(domain=DOMAIN, data=test_fn_user_input.auth).add_to_hass(hass)

    result = await test_fn(
        hass,
        test_fn_user_input,
    )

    assert result
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# OptionsFlow tests
# ---------------------------------------------------------------------------

# Field key and DID derived from tests/components/ecovacs/fixtures/devices/yna5x1/device.json
_OPTION_DEVICE_DID = "E1234567890000000001"
_OPTION_DEVICE_FIELD = _device_pin_field_key(
    {"nick": "Ozmo 950", "did": _OPTION_DEVICE_DID}
)


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Only load the minimum platforms needed for options flow tests."""
    return []


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_show_form(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow shows the camera PINs form with the device field."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "camera_pins"
    assert _OPTION_DEVICE_FIELD in result["data_schema"].schema


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test options flow with no devices creates entry with empty camera pins."""
    controller = mock_config_entry.runtime_data
    with patch.object(type(controller), "devices", new_callable=PropertyMock, return_value=[]):
        result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "camera_pins"
        assert not result["data_schema"].schema

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_CAMERA_PINS: {}}


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_set_valid_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting a valid numeric PIN is encoded and saved."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_OPTION_DEVICE_FIELD: "1234"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CAMERA_PINS][_OPTION_DEVICE_DID] == encode_pin("1234")


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_invalid_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a non-numeric PIN shows an error and re-displays the form."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_OPTION_DEVICE_FIELD: "abcd"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "camera_pins"
    assert result["errors"] == {_OPTION_DEVICE_FIELD: "invalid_camera_pin"}


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_sentinel_keeps_existing_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that submitting the sentinel value preserves the existing hashed PIN."""
    existing_hash = encode_pin("5678")
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CAMERA_PINS: {_OPTION_DEVICE_DID: existing_hash}},
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_OPTION_DEVICE_FIELD: EcovacsOptionsFlowHandler._PIN_ALREADY_SET},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CAMERA_PINS][_OPTION_DEVICE_DID] == existing_hash


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_empty_field_keeps_existing_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that leaving the PIN field blank preserves an existing hashed PIN."""
    existing_hash = encode_pin("5678")
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={CONF_CAMERA_PINS: {_OPTION_DEVICE_DID: existing_hash}},
    )

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_OPTION_DEVICE_FIELD: ""},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CAMERA_PINS][_OPTION_DEVICE_DID] == existing_hash


@pytest.mark.usefixtures("init_integration")
async def test_options_flow_empty_field_no_existing_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that leaving the PIN field blank when no PIN exists creates no entry for that device."""
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={_OPTION_DEVICE_FIELD: ""},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CAMERA_PINS] == {}
