"""Tests for the Mill WiFi switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.mill_wifi.api import MillApiClient
from custom_components.mill_wifi.const import DOMAIN
from custom_components.mill_wifi.coordinator import MillDataCoordinator
from custom_components.mill_wifi.device_capability import (
    EDeviceCapability,
    EDeviceType,
    ELockMode,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

# --- MOCK DATA ---
MOCK_SWITCH_DEVICE_ID = "socket_switch_1"
MOCK_SWITCH_DEVICE_NAME = "Desk Fan Socket"

MOCK_SOCKET_DATA_OFF = {
    MOCK_SWITCH_DEVICE_ID: {
        "deviceId": MOCK_SWITCH_DEVICE_ID,
        "customName": MOCK_SWITCH_DEVICE_NAME,
        "deviceType": {"childType": {"name": EDeviceType.SOCKET_GEN3.value}},
        "isEnabled": False,
        "isConnected": True,
        "deviceSettings": {"reported": {"lock_status": ELockMode.NO_LOCK.value}},
        "capabilities": [
            EDeviceCapability.ONOFF.value,
            EDeviceCapability.CHILD_LOCK.value,
        ],
    }
}

MOCK_SOCKET_DATA_ON_LOCK_ON = {
    MOCK_SWITCH_DEVICE_ID: {
        "deviceId": MOCK_SWITCH_DEVICE_ID,
        "customName": MOCK_SWITCH_DEVICE_NAME,
        "deviceType": {"childType": {"name": EDeviceType.SOCKET_GEN3.value}},
        "isEnabled": True,
        "isConnected": True,
        "deviceSettings": {"reported": {"lock_status": ELockMode.CHILD.value}},
        "capabilities": [
            EDeviceCapability.ONOFF.value,
            EDeviceCapability.CHILD_LOCK.value,
        ],
    }
}


# --- PYTEST FIXTURES ---
@pytest.fixture
def mock_mill_api_client_fixture():
    """Mock api client fixtures."""

    client = MagicMock(spec=MillApiClient)
    client.login = AsyncMock(return_value=None)
    client.async_setup = AsyncMock(return_value=None)
    client.get_all_devices = AsyncMock(
        return_value=[MOCK_SOCKET_DATA_OFF[MOCK_SWITCH_DEVICE_ID]]
    )  # Default
    client.set_switch_capability = AsyncMock(return_value=None)
    client.set_device_power = AsyncMock(return_value=None)
    return client


@pytest.fixture
async def setup_integration_fixture(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Set integration fixtures."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test@example.com", "password": "password"},
        entry_id="test_switch_entry_fixture",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        mock_mill_api_client_fixture.get_all_devices.return_value = [
            MOCK_SOCKET_DATA_OFF[MOCK_SWITCH_DEVICE_ID]
        ]

        assert await hass.config_entries.async_setup(entry.entry_id) is True, (
            "Failed to set up config entry"
        )
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    if not coordinator.data:
        coordinator.data = {
            MOCK_SWITCH_DEVICE_ID: MOCK_SOCKET_DATA_OFF[MOCK_SWITCH_DEVICE_ID]
        }
    await hass.async_block_till_done()
    return entry


# --- TEST CASES ---
async def test_power_switch_creation_and_state(
    hass: HomeAssistant, setup_integration_fixture: MockConfigEntry
):
    """Test the main power switch entity creation and initial state."""

    entity_id = (
        f"{SWITCH_DOMAIN}.{MOCK_SWITCH_DEVICE_NAME.lower().replace(' ', '_')}_power"
    )
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == STATE_OFF


async def test_child_lock_switch_creation_and_state(
    hass: HomeAssistant, setup_integration_fixture: MockConfigEntry
):
    """Test the child lock switch entity creation and initial state."""

    entity_id = f"{SWITCH_DOMAIN}.{MOCK_SWITCH_DEVICE_NAME.lower().replace(' ', '_')}_child_lock"
    state = hass.states.get(entity_id)
    assert state is not None, f"Entity {entity_id} not found"
    assert state.state == STATE_OFF


async def test_power_switch_turn_on(
    hass: HomeAssistant,
    setup_integration_fixture: MockConfigEntry,
    mock_mill_api_client_fixture: MagicMock,
):
    """Test turning the power switch ON."""

    entity_id = (
        f"{SWITCH_DOMAIN}.{MOCK_SWITCH_DEVICE_NAME.lower().replace(' ', '_')}_power"
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_mill_api_client_fixture.set_device_power.assert_called_once_with(
        MOCK_SWITCH_DEVICE_ID, True, MOCK_SOCKET_DATA_OFF[MOCK_SWITCH_DEVICE_ID]
    )


async def test_power_switch_turn_off(
    hass: HomeAssistant, mock_mill_api_client_fixture: MagicMock
):
    """Test turning the power switch OFF."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test", "password": "pwd"},
        entry_id="power_off_entry",
    )
    entry.add_to_hass(hass)

    # Setup with device ON initially
    mock_mill_api_client_fixture.get_all_devices.return_value = [
        MOCK_SOCKET_DATA_ON_LOCK_ON[MOCK_SWITCH_DEVICE_ID]
    ]
    with patch(
        "custom_components.mill_wifi.__init__.MillApiClient",
        return_value=mock_mill_api_client_fixture,
    ), patch.object(
        MillDataCoordinator,
        "async_config_entry_first_refresh",
        AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.data = {
        MOCK_SWITCH_DEVICE_ID: MOCK_SOCKET_DATA_ON_LOCK_ON[MOCK_SWITCH_DEVICE_ID]
    }
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity_id = (
        f"{SWITCH_DOMAIN}.{MOCK_SWITCH_DEVICE_NAME.lower().replace(' ', '_')}_power"
    )
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_mill_api_client_fixture.set_device_power.assert_called_once_with(
        MOCK_SWITCH_DEVICE_ID, False, MOCK_SOCKET_DATA_ON_LOCK_ON[MOCK_SWITCH_DEVICE_ID]
    )


async def test_child_lock_switch_turn_on(
    hass: HomeAssistant,
    setup_integration_fixture: MockConfigEntry,
    mock_mill_api_client_fixture: MagicMock,
):
    """Test turning the child lock switch ON."""

    entity_id = f"{SWITCH_DOMAIN}.{MOCK_SWITCH_DEVICE_NAME.lower().replace(' ', '_')}_child_lock"

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    await hass.async_block_till_done()

    mock_mill_api_client_fixture.set_switch_capability.assert_called_once_with(
        MOCK_SWITCH_DEVICE_ID,
        EDeviceCapability.CHILD_LOCK.value,
        True,
        MOCK_SOCKET_DATA_OFF[MOCK_SWITCH_DEVICE_ID],
    )
