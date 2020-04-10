"""Test the Panasonic Viera config flow."""
from asynctest import patch
from unittest.mock import Mock
from tests.common import MockConfigEntry

from panasonic_viera import (
    RemoteControl,
    SOAPError,
    TV_TYPE_ENCRYPTED,
    TV_TYPE_NONENCRYPTED,
)

from homeassistant import config_entries, setup
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
)

from .const import (
    CONF_ON_ACTION,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_NOT_CONNECTED,
    ERROR_INVALID_PIN_CODE,
    ERROR_UNKNOWN,
)


def get_mock_remote(host="1.2.3.4", encrypted=False, app_id=None, encryption_key=None):
    """Return a mock bridge."""
    mock_remote = Mock()
    mock_remote._host = host
    mock_remote._type = TV_TYPE_ENCRYPTED if encrypted else TV_TYPE_NONENCRYPTED
    mock_remote._app_id = app_id
    mock_remote._enc_key = encryption_key

    return mock_remote


async def test_flow_encrypted(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["errors"] == {}

    mock_remote = get_mock_remote(encrypted=True)

    with patch("panasonic_viera.RemoteControl", return_value=mock_remote,), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"


async def test_flow_non_encrypted(hass):
    mock_remote = get_mock_remote()

    with patch("panasonic_viera.RemoteControl", return_value=mock_remote,), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            config_entries.SOURCE_USER, {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_ON_ACTION: None,
    }


async def test_valid_pin_code(hass):
    mock_remote = get_mock_remote(
        encrypted=True, app_id="test_app_id", encryption_key="test_encryption_key"
    )

    with patch("panasonic_viera.RemoteControl", return_value=mock_remote,), patch(
        "panasonic_viera.RemoteControl.authorize_pin_code", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            "pairing", {CONF_PIN: "1234"},
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "test-name"
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_ON_ACTION: None,
        CONF_APP_ID: "test_app_id",
        CONF_ENCRYPTION_KEY: "test_encryption_key",
    }


async def test_invalid_pin_code(hass):
    mock_remote = get_mock_remote(encrypted=True)

    with patch("panasonic_viera.RemoteControl", return_value=mock_remote,), patch(
        "panasonic_viera.RemoteControl.authorize_pin_code", side_effect=SOAPError,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            "pairing", {CONF_PIN: "1234"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": "linking"}
