"""Fixtures for ISEO Argo BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.iseo_argo_ble.const import (
    CONF_ADDRESS,
    CONF_PRIV_SCALAR,
    CONF_UUID,
    DOMAIN,
)
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_ADDRESS, MOCK_PRIV_SCALAR, MOCK_UUID_HEX

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(
    mock_bluetooth_history: None,
    enable_bluetooth: None,
) -> None:
    """Auto mock bluetooth for all tests — ensures history is patched first."""
    return


@pytest.fixture(autouse=True)
def mock_bluetooth_history() -> Generator[None]:
    """Patch bluetooth manager to avoid dbus calls on non-Linux platforms."""
    with patch(
        "homeassistant.components.bluetooth.manager.async_load_history_from_system",
        return_value=({}, {}),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ISEO Argo BLE config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=format_mac(MOCK_ADDRESS),
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_UUID: MOCK_UUID_HEX,
            CONF_PRIV_SCALAR: MOCK_PRIV_SCALAR,
        },
        options={},
    )


@pytest.fixture
def mock_iseo_client() -> Generator[MagicMock]:
    """Mock the IseoClient class."""
    client = MagicMock()
    client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=None, firmware_info=None)
    )
    client.open_lock = AsyncMock(return_value=None)
    client.gw_open = AsyncMock(return_value=None)
    client.register_user = AsyncMock(return_value=None)
    client.gw_register_log_notif = AsyncMock(return_value=None)
    client.update_ble_device = MagicMock()

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.IseoClient",
            return_value=client,
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.IseoClient",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_derive_private_key() -> Generator[MagicMock]:
    """Mock derive_private_key (CPU-bound crypto)."""
    mock_priv = MagicMock()
    mock_priv.private_numbers.return_value = MagicMock(private_value=12345678)
    with patch(
        "homeassistant.components.iseo_argo_ble.derive_private_key",
        return_value=mock_priv,
    ):
        yield mock_priv
