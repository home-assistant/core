"""Test the Panasonic Viera config flow."""
from unittest.mock import Mock, patch

from panasonic_viera import TV_TYPE_ENCRYPTED, TV_TYPE_NONENCRYPTED, SOAPError
import pytest

from homeassistant import config_entries
from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    DEFAULT_NAME,
    DOMAIN,
    ERROR_INVALID_PIN_CODE,
)
from homeassistant.const import CONF_PIN

from .conftest import (
    MOCK_BASIC_DATA,
    MOCK_CONFIG_DATA,
    MOCK_DEVICE_INFO,
    MOCK_ENCRYPTION_DATA,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="panasonic_viera_setup", autouse=True)
def panasonic_viera_setup_fixture():
    """Patch the Panasonic Viera setup."""
    with patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry",
        return_value=True,
    ):
        yield


def get_mock_remote(
    request_error=None,
    authorize_error=None,
    encrypted=False,
    app_id=None,
    encryption_key=None,
    device_info=MOCK_DEVICE_INFO,
):
    """Return a mock remote."""
    mock_remote = Mock()

    mock_remote.type = TV_TYPE_ENCRYPTED if encrypted else TV_TYPE_NONENCRYPTED
    mock_remote.app_id = app_id
    mock_remote.enc_key = encryption_key

    def request_pin_code(name=None):
        if request_error is not None:
            raise request_error

    mock_remote.request_pin_code = request_pin_code

    def authorize_pin_code(pincode):
        if pincode == "1234":
            return

        if authorize_error is not None:
            raise authorize_error

    mock_remote.authorize_pin_code = authorize_pin_code

    def get_device_info():
        return device_info

    mock_remote.get_device_info = get_device_info

    return mock_remote


async def test_flow_non_encrypted(hass):
    """Test flow without encryption."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO}


async def test_flow_not_connected_error(hass):
    """Test flow with connection error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_unknown_abort(hass):
    """Test flow with unknown error abortion."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_flow_encrypted_not_connected_pin_code_request(hass):
    """Test flow with encryption and PIN code request connection error abortion during pairing request step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, request_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_flow_encrypted_unknown_pin_code_request(hass):
    """Test flow with encryption and PIN code request unknown error abortion during pairing request step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, request_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_flow_encrypted_valid_pin_code(hass):
    """Test flow with encryption and valid PIN code."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(
        encrypted=True,
        app_id="mock-app-id",
        encryption_key="mock-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "1234"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        **MOCK_CONFIG_DATA,
        **MOCK_ENCRYPTION_DATA,
        ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
    }


async def test_flow_encrypted_invalid_pin_code_error(hass):
    """Test flow with encryption and invalid PIN code error during pairing step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=SOAPError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "0000"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_flow_encrypted_not_connected_abort(hass):
    """Test flow with encryption and PIN code connection error abortion during pairing step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_flow_encrypted_unknown_abort(hass):
    """Test flow with encryption and PIN code unknown error abortion during pairing step."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_BASIC_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_flow_non_encrypted_already_configured_abort(hass):
    """Test flow without encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_BASIC_DATA,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_encrypted_already_configured_abort(hass):
    """Test flow with encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=MOCK_BASIC_DATA,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_imported_flow_non_encrypted(hass):
    """Test imported flow without encryption."""

    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {**MOCK_CONFIG_DATA, ATTR_DEVICE_INFO: MOCK_DEVICE_INFO}


async def test_imported_flow_encrypted_valid_pin_code(hass):
    """Test imported flow with encryption and valid PIN code."""

    mock_remote = get_mock_remote(
        encrypted=True,
        app_id="mock-app-id",
        encryption_key="mock-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "1234"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        **MOCK_CONFIG_DATA,
        **MOCK_ENCRYPTION_DATA,
        ATTR_DEVICE_INFO: MOCK_DEVICE_INFO,
    }


async def test_imported_flow_encrypted_invalid_pin_code_error(hass):
    """Test imported flow with encryption and invalid PIN code error during pairing step."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=SOAPError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PIN: "0000"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_imported_flow_encrypted_not_connected_abort(hass):
    """Test imported flow with encryption and PIN code connection error abortion during pairing step."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"


async def test_imported_flow_encrypted_unknown_abort(hass):
    """Test imported flow with encryption and PIN code unknown error abortion during pairing step."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PIN: "0000"},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_imported_flow_not_connected_error(hass):
    """Test imported flow with connection error abortion."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_imported_flow_unknown_abort(hass):
    """Test imported flow with unknown error abortion."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=MOCK_CONFIG_DATA,
        )

    assert result["type"] == "abort"
    assert result["reason"] == "unknown"


async def test_imported_flow_non_encrypted_already_configured_abort(hass):
    """Test imported flow without encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data=MOCK_CONFIG_DATA,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_BASIC_DATA,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_imported_flow_encrypted_already_configured_abort(hass):
    """Test imported flow with encryption and existing config entry abortion."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="0.0.0.0",
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=MOCK_BASIC_DATA,
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
