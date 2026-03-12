"""Test the liebherr integration init."""

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    IceMakerControl,
    IceMakerMode,
    TemperatureControl,
    TemperatureUnit,
    ToggleControl,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)
import pytest

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed


# Test errors during initial get_devices() call in async_setup_entry
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_setup_entry_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Any,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup handles various error conditions."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


# Test errors during get_device() call in coordinator setup (after successful get_devices)
@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (LiebherrAuthenticationError("Invalid API key"), ConfigEntryState.SETUP_ERROR),
        (LiebherrConnectionError("Connection failed"), ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failed", "connection_error"],
)
async def test_coordinator_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test coordinator setup handles device access errors."""
    mock_config_entry.add_to_hass(hass)
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]
    mock_liebherr_client.get_device.side_effect = side_effect

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


NEW_DEVICE = Device(
    device_id="new_device_id",
    nickname="New Fridge",
    device_type=DeviceType.FRIDGE,
    device_name="K2601",
)

NEW_DEVICE_STATE = DeviceState(
    device=NEW_DEVICE,
    controls=[
        TemperatureControl(
            zone_id=1,
            zone_position=ZonePosition.TOP,
            name="Fridge",
            type="fridge",
            value=4,
            target=5,
            min=2,
            max=8,
            unit=TemperatureUnit.CELSIUS,
        ),
        ToggleControl(
            name="supercool",
            type="ToggleControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            value=False,
        ),
        IceMakerControl(
            name="icemaker",
            type="IceMakerControl",
            zone_id=1,
            zone_position=ZonePosition.TOP,
            ice_maker_mode=IceMakerMode.OFF,
            has_max_ice=False,
        ),
    ],
)


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_discovery_no_new_devices(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scan with no new devices does not create entities."""
    # Same devices returned
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE]

    initial_states = len(hass.states.async_all())

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No new entities should be created
    assert len(hass.states.async_all()) == initial_states


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        LiebherrConnectionError("Connection failed"),
        LiebherrAuthenticationError("Auth failed"),
    ],
    ids=["connection_error", "auth_error"],
)
async def test_dynamic_device_discovery_api_error(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test device scan gracefully handles API errors."""
    mock_liebherr_client.get_devices.side_effect = exception

    initial_states = len(hass.states.async_all())

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # No crash, no new entities
    assert len(hass.states.async_all()) == initial_states
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("init_integration")
async def test_dynamic_device_discovery_coordinator_setup_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device scan skips devices that fail coordinator setup."""
    # New device appears but its state fetch fails
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, NEW_DEVICE]

    original_state = copy.deepcopy(MOCK_DEVICE_STATE)
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(original_state)
        if device_id == "test_device_id"
        else (_ for _ in ()).throw(LiebherrConnectionError("Device offline"))
    )

    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # New device should NOT be added
    assert "new_device_id" not in mock_config_entry.runtime_data.coordinators
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_dynamic_device_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are automatically discovered on all platforms."""
    mock_config_entry.add_to_hass(hass)

    all_platforms = [
        Platform.SENSOR,
        Platform.NUMBER,
        Platform.SWITCH,
        Platform.SELECT,
    ]
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", all_platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Initially only the original device exists
    assert hass.states.get("sensor.test_fridge_top_zone") is not None
    assert hass.states.get("sensor.new_fridge") is None

    # Simulate a new device appearing on the account
    mock_liebherr_client.get_devices.return_value = [MOCK_DEVICE, NEW_DEVICE]
    mock_liebherr_client.get_device_state.side_effect = lambda device_id, **kw: (
        copy.deepcopy(
            NEW_DEVICE_STATE if device_id == "new_device_id" else MOCK_DEVICE_STATE
        )
    )

    # Advance time to trigger device scan (5 minute interval)
    freezer.tick(timedelta(minutes=5, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # New device should have entities on all platforms
    state = hass.states.get("sensor.new_fridge")
    assert state is not None
    assert state.state == "4"
    assert hass.states.get("number.new_fridge_setpoint") is not None
    assert hass.states.get("switch.new_fridge_supercool") is not None
    assert hass.states.get("select.new_fridge_icemaker") is not None

    # Original device should still exist
    assert hass.states.get("sensor.test_fridge_top_zone") is not None

    # Runtime data should have both coordinators
    assert "new_device_id" in mock_config_entry.runtime_data.coordinators
    assert "test_device_id" in mock_config_entry.runtime_data.coordinators
