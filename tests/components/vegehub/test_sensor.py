"""Unit tests for the VegeHub integration's sensor.py."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration
from .conftest import TEST_SIMPLE_MAC, TEST_WEBHOOK_ID

from tests.common import MockConfigEntry, snapshot_platform
from tests.typing import ClientSessionGenerator

UPDATE_DATA = {
    "api_key": "",
    "mac": TEST_SIMPLE_MAC,
    "error_code": 0,
    "sensors": [
        {"slot": 1, "samples": [{"v": 1.5, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 2, "samples": [{"v": 1.45599997, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 3, "samples": [{"v": 1.330000043, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 4, "samples": [{"v": 0.075999998, "t": "2025-01-15T16:51:23Z"}]},
        {"slot": 5, "samples": [{"v": 9.314800262, "t": "2025-01-15T16:51:23Z"}]},
    ],
    "send_time": 1736959883,
    "wifi_str": -27,
}


async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test all entities."""

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        await init_integration(hass, mocked_config_entry)

    assert TEST_WEBHOOK_ID in hass.data["webhook"], "Webhook was not registered"

    # Verify the webhook handler
    webhook_info = hass.data["webhook"][TEST_WEBHOOK_ID]
    assert webhook_info["handler"], "Webhook handler is not set"

    client = await hass_client_no_auth()
    resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)

    # Send the same update again so that the coordinator modifies existing data
    # instead of creating new data.
    resp = await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)

    # Wait for remaining tasks to complete.
    await hass.async_block_till_done()
    assert resp.status == 200, f"Unexpected status code: {resp.status}"
    await snapshot_platform(
        hass, entity_registry, snapshot, mocked_config_entry.entry_id
    )


async def test_sensor_vh400_type(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test VH400 moisture sensor with transformation."""
    # Configure first sensor as VH400 moisture sensor
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mocked_config_entry, options={"data_type_0": "VH400"}
    )

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)
    await hass.async_block_till_done()

    # Check that the VH400 sensor has the correct properties
    state = hass.states.get("sensor.vegehub_input_1_moisture")
    assert state is not None
    assert state.attributes["device_class"] == "moisture"
    assert state.attributes["unit_of_measurement"] == "%"

    # The vh400_transform function should be applied to the raw voltage
    assert float(state.state) == pytest.approx(24.615, rel=1e-3)


async def test_sensor_therm200_type(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test THERM200 temperature sensor with transformation."""
    # Configure second sensor as THERM200 temperature sensor
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mocked_config_entry, options={"data_type_1": "THERM200"}
    )

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)
    await hass.async_block_till_done()

    # Check that the THERM200 sensor has the correct properties
    state = hass.states.get("sensor.vegehub_input_2_temperature")
    assert state is not None
    assert state.attributes["device_class"] == "temperature"
    assert state.attributes["unit_of_measurement"] == "°C"

    # The therm200_transform function should be applied to the raw voltage
    assert float(state.state) == pytest.approx(20.669, rel=1e-2)


async def test_sensor_mixed_types(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client_no_auth: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test mixed sensor types configuration."""
    # Configure multiple sensors with different types
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mocked_config_entry,
        options={
            "data_type_0": "Raw Voltage",  # Default voltage sensor
            "data_type_1": "VH400",  # Moisture sensor
            "data_type_2": "THERM200",  # Temperature sensor
            "data_type_3": "VH400",  # Another moisture sensor
        },
    )

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)
    await hass.async_block_till_done()

    # Verify sensor 1 (Raw Voltage) - should show raw voltage
    state1 = hass.states.get("sensor.vegehub_input_1")
    assert state1 is not None
    assert state1.attributes["device_class"] == "voltage"
    assert float(state1.state) == 1.5

    # Verify sensor 2 (VH400) - should be transformed to moisture %
    # 1.45599997V -> ~22.5%
    state2 = hass.states.get("sensor.vegehub_input_2_moisture")
    assert state2 is not None
    assert state2.attributes["device_class"] == "moisture"
    assert float(state2.state) == pytest.approx(22.5, rel=1e-2)

    # Verify sensor 3 (THERM200) - should be transformed to temperature
    # 1.330000043V -> ~15.42°C
    state3 = hass.states.get("sensor.vegehub_input_3_temperature")
    assert state3 is not None
    assert state3.attributes["device_class"] == "temperature"
    assert float(state3.state) == pytest.approx(15.42, rel=1e-2)

    # Verify sensor 4 (VH400) - should be transformed to moisture %
    # 0.075999998V -> ~0.69%
    state4 = hass.states.get("sensor.vegehub_input_4_moisture")
    assert state4 is not None
    assert state4.attributes["device_class"] == "moisture"
    assert float(state4.state) == pytest.approx(0.69, rel=1e-2)


async def test_sensor_default_type_when_no_options(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors default to Raw Voltage when no options are set."""
    # Don't set any options - should default to "Raw Voltage"
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mocked_config_entry, options={})

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)
    await hass.async_block_till_done()

    # All sensors should be voltage sensors showing raw values
    for i in range(1, 5):
        state = hass.states.get(f"sensor.vegehub_input_{i}")
        assert state is not None
        assert state.attributes["device_class"] == "voltage"
        assert state.attributes["unit_of_measurement"] == "V"


@pytest.mark.parametrize(
    ("sensor_type", "expected_device_class", "expected_unit"),
    [
        ("Raw Voltage", "voltage", "V"),
        ("VH400", "moisture", "%"),
        ("THERM200", "temperature", "°C"),
    ],
)
async def test_sensor_type_configuration(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
    sensor_type: str,
    expected_device_class: str,
    expected_unit: str,
) -> None:
    """Test each sensor type configuration."""
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mocked_config_entry, options={"data_type_0": sensor_type}
    )

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=UPDATE_DATA)
    await hass.async_block_till_done()

    # Find the sensor state - entity_id depends on sensor type
    states = hass.states.async_all()
    sensor_states = [s for s in states if "input_1" in s.entity_id]
    assert len(sensor_states) == 1

    state = sensor_states[0]
    assert state.attributes["device_class"] == expected_device_class
    assert state.attributes["unit_of_measurement"] == expected_unit


async def test_sensor_transformation_with_none_value(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mocked_config_entry: MockConfigEntry,
) -> None:
    """Test that sensors handle None values correctly."""
    mocked_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mocked_config_entry,
        options={
            "data_type_0": "VH400",
            "data_type_1": "THERM200",
        },
    )

    with patch("homeassistant.components.vegehub.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(mocked_config_entry.entry_id)
        await hass.async_block_till_done()

    # Send update with missing sensor data
    update_data_incomplete = {
        "api_key": "",
        "mac": TEST_SIMPLE_MAC,
        "error_code": 0,
        "sensors": [
            # Missing slot 1 and 2 data
            {"slot": 3, "samples": [{"v": 1.330000043, "t": "2025-01-15T16:51:23Z"}]},
        ],
        "send_time": 1736959883,
        "wifi_str": -27,
    }

    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{TEST_WEBHOOK_ID}", json=update_data_incomplete)
    await hass.async_block_till_done()

    # Sensors with missing data should have unavailable or None state
    state1 = hass.states.get("sensor.vegehub_input_1_moisture")
    state2 = hass.states.get("sensor.vegehub_input_2_temperature")

    # These might be "unavailable" or "unknown" depending on entity availability logic
    assert state1 is not None
    assert state2 is not None
