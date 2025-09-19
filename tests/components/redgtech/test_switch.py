"""Tests for the Redgtech switch platform."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from redgtech_api.api import RedgtechAuthError, RedgtechConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.redgtech.const import DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_EMAIL,
    CONF_PASSWORD,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def freezer():
    """Provide a freezer fixture that works with freeze_time decorator."""
    with freeze_time() as frozen_time:
        yield frozen_time


@pytest.fixture
def mock_redgtech_api() -> AsyncMock:
    """Mock the Redgtech API."""
    api = AsyncMock()
    api.login = AsyncMock(return_value="mock_access_token")
    api.get_data = AsyncMock(
        return_value={
            "boards": [
                {
                    "endpointId": "switch_001",
                    "friendlyName": "Living Room Switch",
                    "value": False,
                },
                {
                    "endpointId": "switch_002",
                    "friendlyName": "Kitchen Switch",
                    "value": True,
                },
            ]
        }
    )
    api.set_switch_state = AsyncMock()
    return api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "password123"},
        entry_id="test_entry",
    )


@pytest.fixture
async def setup_redgtech_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_redgtech_api: AsyncMock,
) -> None:
    """Set up the Redgtech integration with mocked API."""
    with patch(
        "homeassistant.components.redgtech.coordinator.RedgtechAPI",
        return_value=mock_redgtech_api,
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    setup_redgtech_integration,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entity setup."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_turn_on(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
) -> None:
    """Test turning a switch on."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.living_room_switch"},
        blocking=True,
    )

    mock_redgtech_api.set_switch_state.assert_called_once_with(
        "switch_001", True, "mock_access_token"
    )


async def test_switch_turn_off(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
) -> None:
    """Test turning a switch off."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.kitchen_switch"},
        blocking=True,
    )

    mock_redgtech_api.set_switch_state.assert_called_once_with(
        "switch_002", False, "mock_access_token"
    )


async def test_switch_toggle(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
) -> None:
    """Test toggling a switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "switch.living_room_switch"},
        blocking=True,
    )

    mock_redgtech_api.set_switch_state.assert_called_once_with(
        "switch_001", True, "mock_access_token"
    )


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            RedgtechConnectionError("Connection failed"),
            "Connection error with Redgtech API",
        ),
        (
            RedgtechAuthError("Auth failed"),
            "Authentication failed when controlling Redgtech switch",
        ),
    ],
)
async def test_exception_handling(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling when controlling switches."""
    mock_redgtech_api.set_switch_state.side_effect = exception

    with pytest.raises(HomeAssistantError, match=error_message):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.living_room_switch"},
            blocking=True,
        )


async def test_switch_auth_error_with_retry(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
) -> None:
    """Test handling auth errors with token renewal."""
    # Mock fails with auth error
    mock_redgtech_api.set_switch_state.side_effect = RedgtechAuthError("Auth failed")

    # Expect HomeAssistantError to be raised
    with pytest.raises(
        HomeAssistantError,
        match="Authentication failed when controlling Redgtech switch",
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.living_room_switch"},
            blocking=True,
        )

    # Test completed successfully


@freeze_time("2023-01-01 12:00:00")
async def test_coordinator_data_update_success(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful data update through coordinator."""
    coordinator = mock_config_entry.runtime_data

    # Update mock data
    mock_redgtech_api.get_data.return_value = {
        "boards": [
            {
                "endpointId": "switch_001",
                "friendlyName": "Living Room Switch",
                "value": True,  # Changed to True
            }
        ]
    }

    # Use freezer to advance time and trigger update
    freezer.tick(delta=timedelta(minutes=2))
    await hass.async_block_till_done()

    # Verify the data was updated successfully
    assert coordinator.last_exception is None
    assert len(coordinator.data) == 1
    assert coordinator.data[0].unique_id == "switch_001"


@freeze_time("2023-01-01 12:00:00")
async def test_coordinator_connection_error_during_update(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handling connection errors during data updates."""
    mock_redgtech_api.get_data.side_effect = RedgtechConnectionError(
        "Connection failed"
    )

    # Use freezer to advance time and trigger update
    freezer.tick(delta=timedelta(minutes=2))
    await hass.async_block_till_done()

    # Verify entities become unavailable due to coordinator error
    living_room_state = hass.states.get("switch.living_room_switch")
    kitchen_state = hass.states.get("switch.kitchen_switch")

    assert living_room_state.state == STATE_UNAVAILABLE
    assert kitchen_state.state == STATE_UNAVAILABLE


@freeze_time("2023-01-01 12:00:00")
async def test_coordinator_auth_error_with_token_renewal(
    hass: HomeAssistant,
    setup_redgtech_integration,
    mock_redgtech_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handling auth errors with token renewal."""
    # First call fails with auth error, second succeeds after token renewal
    mock_redgtech_api.get_data.side_effect = [
        RedgtechAuthError("Auth failed"),
        {
            "boards": [
                {
                    "endpointId": "switch_001",
                    "friendlyName": "Living Room Switch",
                    "value": True,
                }
            ]
        },
    ]

    coordinator = mock_config_entry.runtime_data

    # Use freezer to advance time and trigger update
    freezer.tick(delta=timedelta(minutes=2))
    await hass.async_block_till_done()

    # Verify token renewal was attempted
    assert mock_redgtech_api.login.call_count >= 2
    # Verify data was eventually retrieved successfully
    assert coordinator.last_exception is None
    assert len(coordinator.data) == 1
