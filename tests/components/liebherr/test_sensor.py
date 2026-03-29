"""Test the Liebherr sensor platform."""

import copy
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyliebherrhomeapi import (
    Device,
    DeviceState,
    DeviceType,
    TemperatureControl,
    TemperatureUnit,
    ZonePosition,
)
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
    LiebherrTimeoutError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.liebherr.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities with multi-zone device."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_single_zone_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    platforms: list[Platform],
) -> None:
    """Test single zone device uses device name without zone suffix."""
    device = Device(
        device_id="single_zone_id",
        nickname="Single Zone Fridge",
        device_type=DeviceType.FRIDGE,
        device_name="K2601",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    single_zone_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=ZonePosition.TOP,
                name="Fridge",
                type="fridge",
                value=4,
                unit=TemperatureUnit.CELSIUS,
            )
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        single_zone_state
    )

    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.liebherr.PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_multi_zone_with_none_position(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test multi-zone device with None zone_position falls back to no translation key."""
    device = Device(
        device_id="multi_zone_none",
        nickname="Multi Zone Fridge",
        device_type=DeviceType.COMBI,
        device_name="CBNes9999",
    )
    mock_liebherr_client.get_devices.return_value = [device]
    multi_zone_state = DeviceState(
        device=device,
        controls=[
            TemperatureControl(
                zone_id=1,
                zone_position=None,  # None triggers fallback in _get_zone_translation_key
                name="Fridge",
                type="fridge",
                value=5,
                unit=TemperatureUnit.CELSIUS,
            ),
            TemperatureControl(
                zone_id=2,
                zone_position=ZonePosition.BOTTOM,
                name="Freezer",
                type="freezer",
                value=-18,
                unit=TemperatureUnit.CELSIUS,
            ),
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        multi_zone_state
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Zone with None position should have no translation key (fallback)
    zone1_entity = entity_registry.async_get("sensor.multi_zone_fridge_temperature")
    assert zone1_entity is not None
    assert zone1_entity.translation_key is None

    # Zone with valid position should have translation key
    zone2_entity = entity_registry.async_get("sensor.multi_zone_fridge_bottom_zone")
    assert zone2_entity is not None
    assert zone2_entity.translation_key == "bottom_zone"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
@pytest.mark.parametrize(
    "exception",
    [
        LiebherrConnectionError("Connection failed"),
        LiebherrTimeoutError("Timeout"),
    ],
    ids=["connection_error", "timeout_error"],
)
async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test sensor becomes unavailable when coordinator update fails."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available with value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Simulate update error
    mock_liebherr_client.get_device_state.side_effect = exception

    # Advance time to trigger coordinator refresh (60 second interval)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate recovery
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: copy.deepcopy(
        MOCK_DEVICE_STATE
    )

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should recover
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_update_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test authentication error triggers reauth flow."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available with value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Simulate auth error
    mock_liebherr_client.get_device_state.side_effect = LiebherrAuthenticationError(
        "API key revoked"
    )

    # Advance time to trigger coordinator refresh (60 second interval)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Config entry should be in reauth state
    assert mock_config_entry.state is ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert any(
        flow["handler"] == DOMAIN and flow["context"]["source"] == "reauth"
        for flow in flows
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_unavailable_when_control_missing(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor becomes unavailable when temperature control is removed from device."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Device stops reporting controls (e.g., zone removed or API issue)
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    # Advance time to trigger coordinator refresh
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Sensor should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
