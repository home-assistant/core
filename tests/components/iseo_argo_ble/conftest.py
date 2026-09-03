"""Fixtures for ISEO Argo BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import USER_TYPE_BT, USER_TYPE_PIN, USER_TYPE_RFID, UserEntry
import pytest

from homeassistant.components.iseo_argo_ble.const import (
    CONF_ADMIN_PRIV_SCALAR,
    CONF_ADMIN_UUID,
    CONF_PRIV_SCALAR,
    DEFAULT_USER_SUBTYPE,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.helpers.device_registry import format_mac

from . import (
    MOCK_ADDRESS,
    MOCK_ADMIN_PRIV_SCALAR,
    MOCK_ADMIN_UUID_HEX,
    MOCK_PRIV_SCALAR,
    MOCK_UUID_HEX,
)

from tests.common import MockConfigEntry

MOCK_USERS = [
    UserEntry(
        user_type=USER_TYPE_RFID,
        uuid_hex="1111111111111111111111111111aaaa",
        name="Alice",
        inner_subtype=None,
        disabled=False,
    ),
    UserEntry(
        user_type=USER_TYPE_PIN,
        uuid_hex="2222222222222222222222222222bbbb",
        name="Bob",
        inner_subtype=None,
        disabled=True,
    ),
    # Enrolled without a name: only the UUID identifies it.
    UserEntry(
        user_type=USER_TYPE_BT,
        uuid_hex="3333333333333333333333333333cccc",
        name="  ",
        inner_subtype=16,
        disabled=False,
    ),
    # The two identities Home Assistant enrolled for itself; neither gets a
    # credential sensor.
    UserEntry(
        user_type=USER_TYPE_BT,
        uuid_hex=MOCK_UUID_HEX,
        name="Home Assistant",
        inner_subtype=DEFAULT_USER_SUBTYPE,
        disabled=False,
    ),
    UserEntry(
        user_type=USER_TYPE_BT,
        uuid_hex=MOCK_ADMIN_UUID_HEX,
        name="Home Assistant Admin",
        inner_subtype=16,
        disabled=False,
    ),
]


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock ISEO Argo BLE config entry without user management."""
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
def mock_admin_config_entry() -> MockConfigEntry:
    """Return a mock config entry that also carries the admin identity."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="ISEO Lock",
        unique_id=format_mac(MOCK_ADDRESS),
        data={
            CONF_ADDRESS: MOCK_ADDRESS,
            CONF_UUID: MOCK_UUID_HEX,
            CONF_PRIV_SCALAR: MOCK_PRIV_SCALAR,
            CONF_ADMIN_UUID: MOCK_ADMIN_UUID_HEX,
            CONF_ADMIN_PRIV_SCALAR: MOCK_ADMIN_PRIV_SCALAR,
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
        client.read_users = AsyncMock(return_value=list(MOCK_USERS))
        client.set_user_disabled = AsyncMock(return_value=None)
        client.erase_user_by_uuid = AsyncMock(return_value=None)
        yield client


@pytest.fixture(autouse=True)
def _no_settle_delay() -> Generator[None]:
    """Skip the wait the real lock needs after an admin session."""
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.coordinator.ADMIN_SETTLE_DELAY", 0
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.binary_sensor.ADMIN_SETTLE_DELAY", 0
        ),
    ):
        yield


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
        patch(
            "homeassistant.components.iseo_argo_ble.coordinator.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.binary_sensor.async_ble_device_from_address",
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
