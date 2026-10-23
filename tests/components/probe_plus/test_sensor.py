"""Tests for the Probe Plus sensor platform."""

from unittest.mock import MagicMock, create_autospec, patch

from pyprobeplus.parsers.base import ProbeReading
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_probe_plus")
async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor platform."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch("homeassistant.components.bluetooth.async_get_scanner"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dynamic_probe_discovery(
    hass: HomeAssistant,
    mock_probe_plus: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test dynamic discovery of probe entities."""
    mock_probe_plus.device_state.probes = [mock_probe_plus.device_state.probes[0]]
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch("homeassistant.components.bluetooth.async_get_scanner"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.kitchen_fm210_probe_1_temperature") is not None
    assert hass.states.get("sensor.kitchen_fm210_probe_2_temperature") is None
    assert hass.states.get("sensor.kitchen_fm210_probe_2_battery") is None

    probe_2 = create_autospec(ProbeReading, instance=True)
    probe_2.temperature = 22.0
    probe_2.battery = 80
    probe_2.online = True
    mock_probe_plus.device_state.probes.append(probe_2)
    mock_config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    assert (
        state := hass.states.get("sensor.kitchen_fm210_probe_2_temperature")
    ) is not None
    assert state.state == "22.0"
    assert (
        state := hass.states.get("sensor.kitchen_fm210_probe_2_battery")
    ) is not None
    assert state.state == "80"
