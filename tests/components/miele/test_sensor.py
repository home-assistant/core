"""Tests for miele sensor module."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
    """Test sensor state after polling the API for data."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_states_api_push(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
    push_data_and_actions: None,
) -> None:
    """Test sensor state when the API pushes data via SSE."""

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


@pytest.mark.parametrize("load_device_file", ["fridge_freezer.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fridge_freezer_sensor_states(
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
async def test_oven_temperatures_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Parametrized test for verifying temperature sensors for oven devices."""

    check_sensor_state(hass, "sensor.oven", "off", 0)
    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 0)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 0)

    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "oven_scenario/002_on.json", DOMAIN
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven", "on", 1)
    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 1)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 1)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 1)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 1)

    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "oven_scenario/003_set_temperature.json", DOMAIN
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven", "pause", 2)
    check_sensor_state(hass, "sensor.oven_temperature", "21.5", 2)
    check_sensor_state(hass, "sensor.oven_target_temperature", "80.0", 2)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "30.0", 2)

    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "oven_scenario/004_use_probe.json", DOMAIN
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven", "in_use", 3)
    check_sensor_state(hass, "sensor.oven_temperature", "21.83", 3)
    check_sensor_state(hass, "sensor.oven_target_temperature", "25.0", 3)
    check_sensor_state(hass, "sensor.oven_core_temperature", "22.0", 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "unknown", 3)

    mock_miele_client.get_devices.return_value = load_json_object_fixture(
        "oven_scenario/001_off.json", DOMAIN
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven", "off", 3)
    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 3)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 3)
    check_sensor_state(hass, "sensor.oven_core_temperature", "unknown", 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "unknown", 3)


def check_sensor_state(
    hass: HomeAssistant,
    sensor_entity: str,
    expected: str,
    step: int,
):
    """Check the state of sensor matches the expected state."""

    state = hass.states.get(sensor_entity)

    if expected is None:
        assert state is None, (
            f"[{sensor_entity}] Step {step + 1}: got {state.state}, expected nothing"
        )
    else:
        assert state is not None, f"Missing entity: {sensor_entity}"
        assert state.state == expected, (
            f"[{sensor_entity}] Step {step + 1}: got {state.state}, expected {expected}"
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
