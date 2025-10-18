"""Tests for the OpenRGB select platform."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from openrgb.utils import OpenRGBDisconnected
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openrgb.const import DOMAIN, SCAN_INTERVAL
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def select_only() -> Generator[None]:
    """Enable only the select platform."""
    with patch(
        "homeassistant.components.openrgb.PLATFORMS",
        [Platform.SELECT],
    ):
        yield


@pytest.fixture
def mock_profiles() -> list[SimpleNamespace]:
    """Return a list of mock profiles."""
    return [
        SimpleNamespace(name="Gaming"),
        SimpleNamespace(name="Work"),
        SimpleNamespace(name="Rainbow"),
    ]


# Test basic entity setup and configuration
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure entity is correctly assigned to the OpenRGB server device
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entity_entries) == 1
    assert entity_entries[0].device_id == device_entry.id


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_with_profiles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
) -> None:
    """Test select entity with available profiles."""
    mock_openrgb_client.profiles = mock_profiles

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify select entity has profile options
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.attributes.get("options") == ["Gaming", "Work", "Rainbow"]


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_with_no_profiles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> None:
    """Test select entity when no profiles are available."""
    mock_openrgb_client.profiles = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify select entity is unavailable when no profiles exist
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("options") == []


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_option_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
) -> None:
    """Test selecting a profile successfully."""
    mock_openrgb_client.profiles = mock_profiles

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Select a profile
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.test_computer_profile",
            ATTR_OPTION: "Gaming",
        },
        blocking=True,
    )

    # Verify load_profile was called with the correct profile name
    mock_openrgb_client.load_profile.assert_called_once_with("Gaming")


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_option_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
) -> None:
    """Test selecting a profile that doesn't exist."""
    mock_openrgb_client.profiles = mock_profiles

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Try to select a non-existent profile
    # The select platform will validate that the option is in the options list
    with pytest.raises(
        ServiceValidationError,
        match="Option NonExistent is not valid for entity select.test_computer_profile",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_computer_profile",
                ATTR_OPTION: "NonExistent",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_option_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
) -> None:
    """Test selecting a profile with connection error."""
    mock_openrgb_client.profiles = mock_profiles
    mock_openrgb_client.load_profile.side_effect = OpenRGBDisconnected(
        "Connection lost"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Try to select a profile - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_computer_profile",
                ATTR_OPTION: "Gaming",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_option_value_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
) -> None:
    """Test selecting a profile with ValueError."""
    mock_openrgb_client.profiles = mock_profiles
    mock_openrgb_client.load_profile.side_effect = ValueError("Invalid profile data")

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Try to select a profile - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.test_computer_profile",
                ATTR_OPTION: "Gaming",
            },
            blocking=True,
        )


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_profiles_update_on_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that profile list updates when profiles change."""
    # Start with initial profiles
    mock_openrgb_client.profiles = mock_profiles[:2]  # Only Gaming and Work

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify initial profile options
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.attributes.get("options") == ["Gaming", "Work"]

    # Add a new profile
    mock_openrgb_client.profiles = mock_profiles  # All three profiles

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify updated profile options
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.attributes.get("options") == ["Gaming", "Work", "Rainbow"]


@pytest.mark.usefixtures("mock_openrgb_client")
async def test_select_becomes_unavailable_when_profiles_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
    mock_profiles: list[SimpleNamespace],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select becomes unavailable when all profiles are removed."""
    # Start with profiles
    mock_openrgb_client.profiles = mock_profiles

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify select entity is available with profiles
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes.get("options") == ["Gaming", "Work", "Rainbow"]

    # Remove all profiles
    mock_openrgb_client.profiles = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify select entity becomes unavailable
    state = hass.states.get("select.test_computer_profile")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get("options") == []
