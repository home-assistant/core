"""Fixtures for ISEO Argo BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.iseo_argo_ble.const import CONF_PRIV_SCALAR, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_ADDRESS, MOCK_PRIV_SCALAR, MOCK_UUID_HEX

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ISEO Argo BLE config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ISEO Lock",
        unique_id=format_mac(MOCK_ADDRESS),
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_UUID: MOCK_UUID_HEX,
            CONF_PRIV_SCALAR: MOCK_PRIV_SCALAR,
        },
    )


@pytest.fixture
def mock_iseo_client() -> Generator[MagicMock]:
    """Mock the IseoClient class (shared by setup and the config flow)."""
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.IseoClient",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.iseo_argo_ble.config_flow.IseoClient",
            new=client_class,
        ),
    ):
        client = client_class.return_value
        client.read_state = AsyncMock(
            return_value=MagicMock(door_closed=True, firmware_info="FW:  1.2.3")
        )
        client.open_lock = AsyncMock(return_value=None)
        client.gw_open = AsyncMock(return_value=None)
        client.register_user = AsyncMock(return_value=None)
        client.gw_register_log_notif = AsyncMock(return_value=None)
        client.setup_gateway = AsyncMock(return_value=None)
        client.update_ble_device = MagicMock()
        yield client


@pytest.fixture
def mock_ble_device() -> Generator[MagicMock]:
    """Make the lock visible in Home Assistant's bluetooth cache."""
    ble_device = MagicMock()
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=ble_device,
        ),
    ):
        yield ble_device


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
