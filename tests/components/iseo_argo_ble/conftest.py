"""Fixtures for ISEO Argo BLE tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import LockState
import pytest

from homeassistant.components.iseo_argo_ble.const import CONF_PRIV_SCALAR, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import MOCK_ADDRESS, MOCK_PRIV_SCALAR, MOCK_UUID_HEX, setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_monotonic() -> Generator[None]:
    """Pin the poll clock so every advertisement is eligible for a poll."""
    with patch(
        "homeassistant.components.iseo_argo_ble.coordinator.monotonic_time_coarse",
        return_value=0.0,
    ):
        yield


@pytest.fixture
def lock_state() -> LockState:
    """Return the state the mocked lock reports."""
    return LockState(
        door_closed=True,
        firmware_info="FW:  1.2.3",
        battery_level=7,
        aux_battery_low=False,
        invitation_pending=False,
        passage_mode_light=False,
        privacy_mode=False,
        passage_mode_normal=False,
        vip_mode=False,
        operational_mode=0,
    )


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
def mock_iseo_client(lock_state: LockState) -> Generator[MagicMock]:
    """Mock the IseoClient class (shared by the coordinator and the config flow)."""
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.coordinator.IseoClient",
            autospec=True,
        ) as client_class,
        patch(
            "homeassistant.components.iseo_argo_ble.coordinator.derive_private_key",
            return_value=MagicMock(),
        ),
    ):
        client = client_class.return_value
        client.read_state = AsyncMock(return_value=lock_state)
        client.gw_open = AsyncMock(return_value=None)
        client.setup_gateway = AsyncMock(return_value=None)
        client.update_ble_device = MagicMock()
        yield client


@pytest.fixture
async def config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> MockConfigEntry:
    """Set up a loaded ISEO Argo BLE config entry."""
    await setup_integration(hass, mock_config_entry)
    return mock_config_entry
