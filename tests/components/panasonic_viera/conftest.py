"""Test helpers for Panasonic Viera."""

from unittest.mock import AsyncMock, Mock, patch

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
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

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


def get_mock_remote_entity(device_info=MOCK_DEVICE_INFO):
    """Return a mock remote entity."""
    mock_remote = Mock()

    async def async_create_remote_control(during_setup=False):
        return

    mock_remote.async_create_remote_control = AsyncMock(
        side_effect=async_create_remote_control
    )

    async def async_get_device_info():
        return device_info

    mock_remote.async_get_device_info = AsyncMock(side_effect=async_get_device_info)

    async def async_turn_on():
        return

    mock_remote.async_turn_on = AsyncMock(side_effect=async_turn_on)

    async def async_turn_off():
        return

    mock_remote.async_turn_on = AsyncMock(side_effect=async_turn_off)

    async def async_send_key(key):
        return

    mock_remote.async_send_key = AsyncMock(side_effect=async_send_key)

    return mock_remote


@pytest.fixture(name="mock_remote")
def mock_remote_fixture():
    """Patch the remote."""
    mock_remote = get_mock_remote_entity()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        yield mock_remote
