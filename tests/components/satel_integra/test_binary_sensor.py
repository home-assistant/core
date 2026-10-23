"""Test Satel Integra Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import (
    get_output_changed_callback,
    get_zone_changed_callback,
    setup_integration,
    trigger_connection_status_update,
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

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890_zones_1"), mock_config_entry_with_subentries.entry_id
    )

    assert device_entry == snapshot(name="device-zone")

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "1234567890_outputs_1"), mock_config_entry_with_subentries.entry_id
    )
    assert device_entry == snapshot(name="device-output")


@pytest.mark.parametrize(
    ("device_state", "expected_state"),
    [
        (None, STATE_UNKNOWN),
        (False, STATE_OFF),
        (True, STATE_ON),
    ],
)
async def test_binary_sensor_initial_state(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    device_state: bool | None,
    expected_state: str,
) -> None:
    """Test binary sensors have a correct initial state after initialization."""

    # Instantly call callback to ensure we have initial data set
    async def mock_start(**_: object) -> None:
        mock_satel.state.outputs[1].active = device_state
        mock_satel.state.zones[1].violated = device_state
        get_output_changed_callback(mock_satel)()
        get_zone_changed_callback(mock_satel)()

    mock_satel.start = AsyncMock(side_effect=mock_start)

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

    zone_update_method = get_zone_changed_callback(mock_satel)
    output_update_method = get_output_changed_callback(mock_satel)

    mock_satel.state.outputs[1].active = True
    mock_satel.state.zones[1].violated = True
    output_update_method()
    zone_update_method()
    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON

    mock_satel.state.outputs[1].active = False
    mock_satel.state.zones[1].violated = False
    output_update_method()
    zone_update_method()
    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF


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
    zone_update_method = get_zone_changed_callback(mock_satel)
    output_update_method = get_output_changed_callback(mock_satel)
    output_update_method()
    zone_update_method()

    assert first_reported != hass.states.get("binary_sensor.zone").last_reported
    assert len(events) == 2  # last_reported shall not fire state_changed


async def test_availability(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test availability."""
    entity_id = "binary_sensor.zone"

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get(entity_id).state == STATE_OFF

    await trigger_connection_status_update(hass, mock_satel, False)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    await trigger_connection_status_update(hass, mock_satel, True)

    assert hass.states.get(entity_id).state == STATE_OFF
