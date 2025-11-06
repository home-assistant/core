"""Test Roborock Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.satel_integra.const import (
    SIGNAL_OUTPUTS_UPDATED,
    SIGNAL_ZONES_UPDATED,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, async_dispatcher_send, snapshot_platform


@pytest.fixture(autouse=True)
async def binary_sensor_only() -> AsyncGenerator[None]:
    """Enable only the binary sensor platform."""
    with patch(
        "homeassistant.components.satel_integra.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        yield


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensors correctly being set up."""

    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_with_subentries.entry_id
    )


async def test_binary_sensor_initial_state_off(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors have a correct initial state OFF after initialization."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF


async def test_binary_sensor_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors have a correct initial state ON after initialization."""
    mock_satel.return_value.violated_zones = [1]
    mock_satel.return_value.violated_outputs = [1]

    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON


async def test_binary_sensor_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors have a correct initial state ON after initialization."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_with_subentries.state is ConfigEntryState.LOADED

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    # Should do nothing, only react to it's own number
    async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, {2: 1})
    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {2: 1})

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    async_dispatcher_send(hass, SIGNAL_ZONES_UPDATED, {1: 1})
    async_dispatcher_send(hass, SIGNAL_OUTPUTS_UPDATED, {1: 1})

    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON
