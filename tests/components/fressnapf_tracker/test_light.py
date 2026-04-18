"""Test the Fressnapf Tracker light platform."""

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

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform

TRACKER_NO_LED = Tracker(
    name="Fluffy",
    battery=0,
    charging=False,
    position=None,
    tracker_settings=TrackerSettings(
        generation="GPS Tracker 2.0",
        features=TrackerFeatures(flash_light=False, live_tracking=True),
    ),
)


@pytest.fixture(autouse=True)
async def platforms() -> AsyncGenerator[None]:
    """Return the platforms to be loaded for this test."""
    with patch(
        "homeassistant.components.fressnapf_tracker.PLATFORMS", [Platform.LIGHT]
    ):
        yield


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test light entity is created correctly."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_auth_client")
async def test_not_added_when_no_led(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
) -> None:
    """Test light entity is created correctly."""
    mock_api_client_init.get_tracker.return_value = TRACKER_NO_LED

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
    """Test turning the light on."""
    entity_id = "light.fluffy_flashlight"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api_client_coordinator.set_led_brightness.assert_called_once_with(100)


@pytest.mark.usefixtures("init_integration")
async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_api_client_coordinator: MagicMock,
) -> None:
    """Test turning the light on with brightness."""
    entity_id = "light.fluffy_flashlight"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # 128/255 * 100 = 50
    mock_api_client_coordinator.set_led_brightness.assert_called_once_with(50)


@pytest.mark.usefixtures("init_integration")
async def test_turn_off(
    hass: HomeAssistant,
    mock_api_client_coordinator: MagicMock,
) -> None:
    """Test turning the light off."""
    entity_id = "light.fluffy_flashlight"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_api_client_coordinator.set_led_brightness.assert_called_once_with(0)


@pytest.mark.parametrize(
    "activatable_parameter",
    [
        "seen_recently",
        "nonempty_battery",
        "not_charging",
    ],
)
@pytest.mark.usefixtures("mock_auth_client")
async def test_turn_on_led_not_activatable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
    mock_api_client_coordinator: MagicMock,
    activatable_parameter: str,
) -> None:
    """Test turning on the light when LED is not activatable raises."""
    setattr(
        mock_api_client_init.get_tracker.return_value.led_activatable,
        activatable_parameter,
        False,
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "light.fluffy_flashlight"

    with pytest.raises(HomeAssistantError, match="The flashlight cannot be activated"):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    mock_api_client_coordinator.set_led_brightness.assert_not_called()


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

    entity_id = "light.fluffy_flashlight"

    mock_api_client_coordinator.set_led_brightness.side_effect = api_exception
    with pytest.raises(expected_exception):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
