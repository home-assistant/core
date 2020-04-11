"""Test the Panasonic Viera config flow."""
from unittest.mock import Mock

from asynctest import patch
from panasonic_viera import (
    TV_TYPE_ENCRYPTED,
    TV_TYPE_NONENCRYPTED,
    RemoteControl,
    SOAPError,
)

from homeassistant import config_entries, setup
from homeassistant.components.panasonic_viera.const import (
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_INVALID_PIN_CODE,
    ERROR_NOT_CONNECTED,
    ERROR_UNKNOWN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PIN, CONF_PORT

from tests.common import MockConfigEntry


def get_mock_remote(
    host="1.2.3.4",
    fail_authorize_connection=False,
    encrypted=False,
    app_id=None,
    encryption_key=None,
):
    """Return a mock remote."""
    mock_remote = Mock()
    mock_remote._host = host
    mock_remote._type = TV_TYPE_ENCRYPTED if encrypted else TV_TYPE_NONENCRYPTED
    mock_remote._app_id = app_id
    mock_remote._enc_key = encryption_key

    def request_pin_code(name=None):
        return

    mock_remote.request_pin_code = request_pin_code

    def authorize_pin_code(pincode):
        if pincode == "1234":
            return

        if fail_authorize_connection:
            raise TimeoutError
        else:
            raise SOAPError

    mock_remote.authorize_pin_code = authorize_pin_code

    return mock_remote


async def test_flow_non_encrypted(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
<<<<<<< HEAD
<<<<<<< HEAD
    assert result["step_id"] == "user"

<<<<<<< HEAD
    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
=======
    assert result["errors"] == {}
=======
    assert result["step_id"] == "user"
>>>>>>> Commit before rebase

    mock_remote = get_mock_remote(encrypted=True)

    with patch("panasonic_viera.RemoteControl", return_value=mock_remote,), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
>>>>>>> Commit before rebase
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result2["type"] == "form"
    assert result2["step_id"] == "pairing"
    assert result2["errors"] == {}

<<<<<<< HEAD
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_UNKNOWN}


async def test_flow_not_connected(hass):
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
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_flow_unknown_error(hass):
    """Test flow with unknown error."""

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
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_UNKNOWN}


async def test_flow_already_configured_non_encrypted(hass):
    """Test flow without encryption and existing config entry."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME, CONF_PORT: DEFAULT_PORT},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_already_configured_encrypted(hass):
    """Test flow with encryption and existing config entry."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_APP_ID: "test-app-id",
            CONF_ENCRYPTION_KEY: "test-encryption-key",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
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
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
=======

async def test_flow_non_encrypted(hass):
=======
>>>>>>> Commit before rebase
    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "create_entry"
<<<<<<< HEAD
    assert result["title"] == "test-name"
>>>>>>> Commit before rebase
=======
    assert result["title"] == DEFAULT_NAME
>>>>>>> Commit before rebase
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
<<<<<<< HEAD
        CONF_ON_ACTION: "test-on-action",
    }


async def test_imported_flow_encrypted_valid_pin_code(hass):
    """Test imported flow with encryption and valid PIN code."""

    mock_remote = get_mock_remote(
        encrypted=True, app_id="test-app-id", encryption_key="test-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "1234"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
=======
        CONF_ON_ACTION: None,
    }


async def test_flow_encrypted_valid_pin_code(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(
        encrypted=True, app_id="test-app-id", encryption_key="test-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "1234"},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_ON_ACTION: None,
        CONF_APP_ID: "test-app-id",
        CONF_ENCRYPTION_KEY: "test-encryption-key",
    }


async def test_flow_encrypted_invalid_pin_code(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "0000"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_flow_encrypted_invalid_pin_code_not_connected(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    mock_remote = get_mock_remote(encrypted=True, fail_authorize_connection=True)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_flow_encrypted_not_connected(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_flow_already_configured_encrypted(hass):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_APP_ID: "test-app-id",
            CONF_ENCRYPTION_KEY: "test-encryption-key",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_flow_already_configured_non_encrypted(hass):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME, CONF_PORT: DEFAULT_PORT},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_imported_flow_non_encrypted(hass):
    mock_remote = get_mock_remote(encrypted=False)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_NAME
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
        CONF_ON_ACTION: "test-on-action",
    }


async def test_imported_flow_encrypted_valid_pin_code(hass):
    mock_remote = get_mock_remote(
        encrypted=True, app_id="test-app-id", encryption_key="test-encryption-key",
    )

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "1234"},
    )

    assert result["type"] == "create_entry"
<<<<<<< HEAD
    assert result["title"] == "test-name"
>>>>>>> Commit before rebase
=======
    assert result["title"] == DEFAULT_NAME
>>>>>>> Commit before rebase
    assert result["data"] == {
        CONF_HOST: "1.2.3.4",
        CONF_NAME: DEFAULT_NAME,
        CONF_PORT: DEFAULT_PORT,
<<<<<<< HEAD
<<<<<<< HEAD
        CONF_ON_ACTION: "test-on-action",
        CONF_APP_ID: "test-app-id",
        CONF_ENCRYPTION_KEY: "test-encryption-key",
    }


async def test_imported_flow_encrypted_invalid_pin_code(hass):
    """Test imported flow with encryption and invalid PIN code."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=SOAPError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PIN: "0000"},
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}


async def test_imported_flow_encrypted_pin_code_not_connected(hass):
    """Test imported flow with encryption and PIN code connection error."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=TimeoutError)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
=======
        CONF_ON_ACTION: None,
        CONF_APP_ID: "test_app_id",
        CONF_ENCRYPTION_KEY: "test_encryption_key",
=======
        CONF_ON_ACTION: "test-on-action",
        CONF_APP_ID: "test-app-id",
        CONF_ENCRYPTION_KEY: "test-encryption-key",
>>>>>>> Commit before rebase
    }


async def test_imported_flow_encrypted_invalid_pin_code(hass):
    mock_remote = get_mock_remote(encrypted=True)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_configure(
<<<<<<< HEAD
            "pairing", {CONF_PIN: "1234"},
>>>>>>> Commit before rebase
=======
            result["flow_id"], {CONF_PIN: "0000"},
>>>>>>> Commit before rebase
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"
<<<<<<< HEAD
<<<<<<< HEAD

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_imported_flow_encrypted_pin_code_unknown_error(hass):
    """Test imported flow with encryption and PIN code unknown error."""

    mock_remote = get_mock_remote(encrypted=True, authorize_error=Exception)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_UNKNOWN}


async def test_imported_flow_not_connected(hass):
    """Test imported flow with connection error."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_imported_flow_unknown_error(hass):
    """Test imported flow with unknown error."""

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_UNKNOWN}


async def test_imported_flow_already_configured_non_encrypted(hass):
    """Test imported flow without encryption and existing config entry."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_ON_ACTION: "test-on-action",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_imported_flow_already_configured_encrypted(hass):
    """Test imported flow with encryption and existing config entry."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_ON_ACTION: "test-on-action",
            CONF_APP_ID: "test-app-id",
            CONF_ENCRYPTION_KEY: "test-encryption-key",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
=======
    assert result["errors"] == {"base": "linking"}
>>>>>>> Commit before rebase
=======
    assert result["errors"] == {"base": ERROR_INVALID_PIN_CODE}
<<<<<<< HEAD
>>>>>>> Commit before rebase
=======


async def test_imported_flow_encrypted_invalid_pin_code_not_connected(hass):
    mock_remote = get_mock_remote(encrypted=True, fail_authorize_connection=True)

    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        return_value=mock_remote,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "pairing"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_PIN: "0000"},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_imported_flow_not_connected(hass):
    with patch(
        "homeassistant.components.panasonic_viera.config_flow.RemoteControl",
        side_effect=TimeoutError,
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup", return_value=True
    ), patch(
        "homeassistant.components.panasonic_viera.async_setup_entry", return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                CONF_HOST: "1.2.3.4",
                CONF_NAME: DEFAULT_NAME,
                CONF_PORT: DEFAULT_PORT,
                CONF_ON_ACTION: "test-on-action",
            },
        )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": ERROR_NOT_CONNECTED}


async def test_imported_flow_already_configured_encrypted(hass):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_ON_ACTION: "test-on-action",
            CONF_APP_ID: "test-app-id",
            CONF_ENCRYPTION_KEY: "test-encryption-key",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_imported_flow_already_configured_non_encrypted(hass):
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.2.3.4",
        data={
            CONF_HOST: "1.2.3.4",
            CONF_NAME: DEFAULT_NAME,
            CONF_PORT: DEFAULT_PORT,
            CONF_ON_ACTION: "test-on-action",
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_HOST: "1.2.3.4", CONF_NAME: DEFAULT_NAME},
    )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
>>>>>>> Commit before rebase
