"""Test the Fressnapf Tracker switch platform."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from fressnapftracker import (
    FressnapfTrackerError,
    FressnapfTrackerInvalidTokenError,
    Tracker,
    TrackerFeatures,
    TrackerSettings,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TRACKER_NO_ENERGY_SAVING_MODE = Tracker(
    name="Fluffy",
    battery=0,
    charging=False,
    position=None,
    tracker_settings=TrackerSettings(
        generation="GPS Tracker 2.0",
        features=TrackerFeatures(energy_saving_mode=False),
    ),
)


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS", [Platform.SWITCH]
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_auth_client")
async def test_not_added_when_no_energy_saving_mode(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
) -> None:
    """Test switch entity is created correctly."""
    mock_api_client_init.get_tracker.return_value = TRACKER_NO_ENERGY_SAVING_MODE

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 0


@pytest.mark.usefixtures("init_integration")
async def test_turn_on(
    hass: HomeAssistant,
    mock_api_client_coordinator: MagicMock,
) -> None:
    """Test turning the switch on."""
    entity_id = "switch.fluffy_sleep_mode"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api_client_coordinator.set_energy_saving.assert_called_once_with(True)


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_api_client_coordinator: MagicMock,
) -> None:
    """Test turning the switch off."""
    entity_id = "switch.fluffy_sleep_mode"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api_client_coordinator.set_energy_saving.assert_called_once_with(False)


@pytest.mark.parametrize(
    ("api_exception", "expected_exception"),
    [
        (FressnapfTrackerError("Something went wrong"), HomeAssistantError),
        (
            FressnapfTrackerInvalidTokenError("Token no longer valid"),
            ConfigEntryAuthFailed,
        ),
    ],
)
@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
@pytest.mark.usefixtures("mock_auth_client", "mock_api_client_init")
async def test_turn_on_off_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_coordinator: MagicMock,
    api_exception: FressnapfTrackerError,
    expected_exception: type[HomeAssistantError],
    service: str,
) -> None:
    """Test that errors during service handling are handled correctly."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "switch.fluffy_sleep_mode"

    mock_api_client_coordinator.set_energy_saving.side_effect = api_exception
    with pytest.raises(expected_exception):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
