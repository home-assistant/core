"""Test Satel Integra Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import get_monitor_callbacks, setup_integration

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)


@pytest.fixture(autouse=True)
async def binary_sensor_only() -> AsyncGenerator[None]:
    """Enable only the binary sensor platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


@pytest.mark.usefixtures("mock_satel")
async def test_binary_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test binary sensors correctly being set up."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subentries.entry_id
    )

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "1234567890_zones_1")}
    )

    assert device_entry == snapshot(name="device-zone")

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, "1234567890_outputs_1")}
    )
    assert device_entry == snapshot(name="device-output")


@pytest.mark.parametrize(
    ("violated_entries", "expected_state"),
    [
        ({2: 1}, STATE_UNKNOWN),
        ({1: 0}, STATE_OFF),
        ({1: 1}, STATE_ON),
    ],
)
async def test_binary_sensor_initial_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    violated_entries: dict[int, int],
    expected_state: str,
) -> None:
    """Test binary sensors have a correct initial state after initialization."""

    # Instantly call callback to ensure we have initial data set
    async def mock_monitor_callback(
        alarm_status_callback, zones_callback, outputs_callback
    ):
        outputs_callback({"outputs": violated_entries})
        zones_callback({"zones": violated_entries})

    mock_satel.monitor_status = AsyncMock(side_effect=mock_monitor_callback)

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == expected_state
    assert hass.states.get("binary_sensor.output").state == expected_state


async def test_binary_sensor_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors correctly change state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    _, zone_update_method, output_update_method = get_monitor_callbacks(mock_satel)

    output_update_method({"outputs": {1: 1}})
    zone_update_method({"zones": {1: 1}})
    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON

    output_update_method({"outputs": {1: 0}})
    zone_update_method({"zones": {1: 0}})
    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    # The client library should always report all entries, but test that we set the status correctly if it doesn't
    output_update_method({"outputs": {2: 1}})
    zone_update_method({"zones": {2: 1}})
    assert hass.states.get("binary_sensor.zone").state == STATE_UNKNOWN
    assert hass.states.get("binary_sensor.output").state == STATE_UNKNOWN


async def test_binary_sensor_last_reported(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensors update last_reported if same state is reported."""
    events = async_capture_events(hass, "state_changed")
    await setup_integration(hass, mock_config_entry_with_subentries)

    first_reported = hass.states.get("binary_sensor.zone").last_reported
    assert first_reported is not None
    # Initial 2 state change events for both zone and output
    assert len(events) == 2

    freezer.tick(1)
    async_fire_time_changed(hass)

    # Run callbacks with same payload
    _, zone_update_method, output_update_method = get_monitor_callbacks(mock_satel)
    output_update_method({"outputs": {1: 0}})
    zone_update_method({"zones": {1: 0}})

    assert first_reported != hass.states.get("binary_sensor.zone").last_reported
    assert len(events) == 2  # last_reported shall not fire state_changed
