"""Test the APSystem binary sensor module."""

import datetime
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

SCAN_INTERVAL = datetime.timedelta(seconds=12)


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch(
        "homeassistant.components.apsystems.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


async def test_connection_status_online(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection status sensor is on when inverter is reachable."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.mock_title_inverter_connection_status")
    assert state is not None
    assert state.state == "on"


async def test_connection_status_offline(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection status sensor turns off when inverter goes offline."""
    await setup_integration(hass, mock_config_entry)

    # Simulate inverter going offline
    mock_apsystems.get_output_data.side_effect = ConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.mock_title_inverter_connection_status")
    assert state is not None
    assert state.state == "off"


async def test_connection_status_timeout(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection status sensor turns off on timeout."""
    await setup_integration(hass, mock_config_entry)

    mock_apsystems.get_output_data.side_effect = TimeoutError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.mock_title_inverter_connection_status")
    assert state is not None
    assert state.state == "off"


async def test_connection_status_recovery(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test connection status sensor recovers after inverter comes back online."""
    await setup_integration(hass, mock_config_entry)

    # Go offline
    mock_apsystems.get_output_data.side_effect = ConnectionError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.mock_title_inverter_connection_status").state
        == "off"
    )

    # Come back online
    mock_apsystems.get_output_data.side_effect = None
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("binary_sensor.mock_title_inverter_connection_status").state
        == "on"
    )


async def test_connection_status_cold_start_offline(
    hass: HomeAssistant,
    mock_apsystems: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test connection status is off when inverter is offline from the start."""
    mock_apsystems.get_device_info.side_effect = TimeoutError
    mock_apsystems.get_output_data.side_effect = TimeoutError
    mock_apsystems.get_alarm_info.side_effect = TimeoutError

    with patch(
        "homeassistant.components.apsystems.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.mock_title_inverter_connection_status")
    assert state is not None
    assert state.state == "off"
