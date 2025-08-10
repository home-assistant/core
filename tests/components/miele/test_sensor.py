"""Tests for miele sensor module."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pymiele import MieleDevices
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.miele.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)


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


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_oven_temperatures_scenario(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    setup_platform: None,
    mock_config_entry: MockConfigEntry,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Parametrized test for verifying temperature sensors for oven devices."""

    # Initial state when the oven is and created for the first time - don't know if it supports core temperature (probe)
    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 0)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 0)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 0)

    # Simulate temperature settings, no probe temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = 8000
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        80.0
    )
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = 2150
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = 21.5

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "21.5", 1)
    check_sensor_state(hass, "sensor.oven_target_temperature", "80.0", 1)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 1)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 1)

    # Simulate unsetting temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        None
    )
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = None

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 2)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 2)
    check_sensor_state(hass, "sensor.oven_core_temperature", None, 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", None, 2)

    # Simulate temperature settings with probe temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = 8000
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        80.0
    )
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0]["value_raw"] = 3000
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_localized"
    ] = 30.0
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = 2183
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = 21.83
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = 2200
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = 22.0

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "21.83", 3)
    check_sensor_state(hass, "sensor.oven_target_temperature", "80.0", 3)
    check_sensor_state(hass, "sensor.oven_core_temperature", "22.0", 2)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "30.0", 3)

    # Simulate unsetting temperature
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["targetTemperature"][0]["value_localized"] = (
        None
    )
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_raw"
    ] = -32768
    device_fixture["DummyOven"]["state"]["coreTargetTemperature"][0][
        "value_localized"
    ] = None
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["temperature"][0]["value_localized"] = None
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = -32768
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = None

    freezer.tick(timedelta(seconds=130))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    check_sensor_state(hass, "sensor.oven_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_target_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_core_temperature", "unknown", 4)
    check_sensor_state(hass, "sensor.oven_core_target_temperature", "unknown", 4)


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


@pytest.mark.parametrize("load_device_file", ["oven.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
async def test_temperature_sensor_registry_lookup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_miele_client: MagicMock,
    setup_platform: None,
    device_fixture: MieleDevices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that core temperature sensor is provided by the integration after looking up in entity registry."""

    # Initial state, the oven is showing core temperature (probe)
    freezer.tick(timedelta(seconds=130))
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_raw"] = 2200
    device_fixture["DummyOven"]["state"]["coreTemperature"][0]["value_localized"] = 22.0
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = "sensor.oven_core_temperature"

    assert hass.states.get(entity_id) is not None
    assert hass.states.get(entity_id).state == "22.0"

    # reload device when turned off, reporting the invalid value
    mock_miele_client.get_devices.return_value = await async_load_json_object_fixture(
        hass, "oven.json", DOMAIN
    )

    # unload config entry and reload to make sure that the entity is still provided
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unavailable"

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "unknown"


@pytest.mark.parametrize("load_device_file", ["vacuum_device.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_vacuum_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test robot vacuum cleaner sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


@pytest.mark.parametrize("load_device_file", ["fan_devices.json"])
@pytest.mark.parametrize("platforms", [(SENSOR_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fan_hob_sensor_states(
    hass: HomeAssistant,
    mock_miele_client: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: None,
) -> None:
    """Test robot fan / hob sensor state."""

    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)
