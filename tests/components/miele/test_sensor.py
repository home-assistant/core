"""Tests for miele sensor module."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .mocks import mock_sensor_transitions

from tests.common import MockConfigEntry, load_json_object_fixture, snapshot_platform


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["hob.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_hob_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["oven_scenario/001_off.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.parametrize(
    ("device_name", "json_sequence", "expected_sensor_states"),
    [
        (
            "oven",
            [
                "oven_scenario/002_on.json",
                "oven_scenario/003_set_temperature.json",
                "oven_scenario/004_use_probe.json",
                "oven_scenario/001_off.json",
            ],
            {
                "": ["off", "on", "pause", "in_use", "off"],
                "temperature": ["unknown", "unknown", "21.5", "21.83", "unknown"],
                "target_temperature": ["unknown", "unknown", "80.0", "25.0", "unknown"],
                "core_temperature": [None, None, None, "22.0", "unknown"],
                "core_target_temperature": [None, None, "30.0", "unknown", "unknown"],
            },
        ),
    ],
)
async def test_oven_temperatures_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_name: str,
    json_sequence: list[str],
    expected_sensor_states: dict[str, list[str]],
) -> None:
    """Parametrized test for verifying temperature sensors for oven devices."""

    await mock_sensor_transitions(
        hass,
        mock_miele_client,
        mock_config_entry,
        device_name,
        json_sequence,
        expected_sensor_states,
    )


@pytest.mark.parametrize("load_device_file", ["oven_scenario/004_use_probe.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_temperature_sensor_registry_lookup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    setup_platform: None,
) -> None:
    """Test that core temperature sensor is provided by the integration after looking up in entity registry."""

    entity_id = "sensor.oven_core_temperature"

    assert hass.states.get(entity_id) is not None
    assert hass.states.get(entity_id).state == "22.0"

    # reload device when turned off, reporting the invalid value
    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "oven_scenario/001_off.json", DOMAIN
    )

    # unload config entry and reload to make sure that the entity is still provided
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"
