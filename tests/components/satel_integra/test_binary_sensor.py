"""Test Satel Integra Binary Sensor."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import STATE_OFF, STATE_ON
from homeassistant.components.satel_integra.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


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


async def test_binary_sensor_initial_state_on(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors have a correct initial state ON after initialization."""
    mock_satel.violated_zones = [1]
    mock_satel.violated_outputs = [1]

    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON


async def test_binary_sensor_callback(
    hass: HomeAssistant,
    mock_satel: AsyncMock,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test binary sensors correctly change state after a callback from the panel."""
    await setup_integration(hass, mock_config_entry_with_subentries)

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    monitor_status_call = mock_satel.monitor_status.call_args_list[0][0]
    output_update_method = monitor_status_call[2]
    zone_update_method = monitor_status_call[1]

    # Should do nothing, only react to it's own number
    output_update_method({"outputs": {2: 1}})
    zone_update_method({"zones": {2: 1}})

    assert hass.states.get("binary_sensor.zone").state == STATE_OFF
    assert hass.states.get("binary_sensor.output").state == STATE_OFF

    output_update_method({"outputs": {1: 1}})
    zone_update_method({"zones": {1: 1}})

    assert hass.states.get("binary_sensor.zone").state == STATE_ON
    assert hass.states.get("binary_sensor.output").state == STATE_ON
