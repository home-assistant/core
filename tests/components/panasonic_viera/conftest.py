"""Test helpers for Panasonic Viera."""

from unittest.mock import Mock, patch

from panasonic_viera import TV_TYPE_ENCRYPTED, TV_TYPE_NONENCRYPTED
import pytest

from homeassistant.components.panasonic_viera.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL_NUMBER,
    ATTR_UDN,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NUMBER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from tests.common import MockConfigEntry

MOCK_BASIC_DATA = {
    CONF_HOST: "0.0.0.0",
    CONF_NAME: DEFAULT_NAME,
}

MOCK_CONFIG_DATA = {
    **MOCK_BASIC_DATA,
    CONF_PORT: DEFAULT_PORT,
    CONF_ON_ACTION: None,
}

MOCK_ENCRYPTION_DATA = {
    CONF_APP_ID: "mock-app-id",
    CONF_ENCRYPTION_KEY: "mock-encryption-key",
}

MOCK_DEVICE_INFO = {
    ATTR_FRIENDLY_NAME: DEFAULT_NAME,
    ATTR_MANUFACTURER: DEFAULT_MANUFACTURER,
    ATTR_MODEL_NUMBER: DEFAULT_MODEL_NUMBER,
    ATTR_UDN: "mock-unique-id",
}


def get_mock_remote(
    request_error=None,
    authorize_error=None,
    encrypted=False,
    app_id=None,
    encryption_key=None,
    device_info: UndefinedType | None = UNDEFINED,
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

    mock_remote.get_device_info = Mock(
        return_value=MOCK_DEVICE_INFO if device_info is UNDEFINED else device_info
    )

    mock_remote.send_key = Mock()

    mock_remote.get_volume = Mock(return_value=100)

    return mock_remote


@pytest.fixture(name="mock_remote")
def mock_remote_fixture():
    """Patch the library remote."""
    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.RemoteControl",
        return_value=mock_remote,
    ):
        yield mock_remote


@pytest.fixture
async def init_integration(hass: HomeAssistant, mock_remote: Mock) -> MockConfigEntry:
    """Set up the Panasonic Viera integration for testing."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry
