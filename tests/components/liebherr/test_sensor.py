"""Test the Liebherr sensor platform."""

import copy
from dataclasses import replace
from unittest.mock import MagicMock, patch

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
from homeassistant.helpers.event import async_track_state_change_event

from .conftest import MOCK_DEVICE, MOCK_DEVICE_STATE, SSEStreamHelper

from tests.common import MockConfigEntry, snapshot_platform


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
    """Test multi-zone device with None zone_position falls back."""
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
                # None triggers fallback in _get_zone_translation_key
                zone_position=None,
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
    sse_helper: SSEStreamHelper,
    exception: Exception,
) -> None:
    """Test sensor becomes unavailable when the stream disconnects."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available with value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Simulate a stream disconnect via the mocked ``get_device_state``.
    mock_liebherr_client.get_device_state.side_effect = exception

    await sse_helper.async_push()

    # Sensor should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Simulate reconnect with a changed top-zone temperature.
    fresh_state = replace(
        MOCK_DEVICE_STATE,
        controls=[
            replace(control, value=6)
            if isinstance(control, TemperatureControl) and control.zone_id == 1
            else control
            for control in MOCK_DEVICE_STATE.controls
        ],
    )
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: fresh_state
    reconnect_states: list[str] = []
    unsubscribe = async_track_state_change_event(
        hass,
        entity_id,
        lambda event: reconnect_states.append(event.data["new_state"].state),
    )

    await sse_helper.async_reconnect()
    unsubscribe()

    # Sensor should recover directly with fresh data, without exposing stale data.
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "6"
    assert reconnect_states == ["6"]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_sensor_update_auth_failure_triggers_reauth(
    hass: HomeAssistant,
    mock_liebherr_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    sse_helper: SSEStreamHelper,
) -> None:
    """Test authentication error triggers reauth flow."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available with value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Simulate auth error from the SSE stream
    mock_liebherr_client.get_device_state.side_effect = LiebherrAuthenticationError(
        "API key revoked"
    )

    await sse_helper.async_push()

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
    sse_helper: SSEStreamHelper,
) -> None:
    """Test sensor becomes unavailable when control is removed."""
    entity_id = "sensor.test_fridge_top_zone"

    # Initial state should be available
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "5"

    # Device stops reporting controls (e.g., zone removed or API issue).
    # Only observable via a full-state event on stream reconnect.
    mock_liebherr_client.get_device_state.side_effect = lambda *a, **kw: DeviceState(
        device=MOCK_DEVICE, controls=[]
    )

    await sse_helper.async_reconnect()

    # Sensor should now be unavailable
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
