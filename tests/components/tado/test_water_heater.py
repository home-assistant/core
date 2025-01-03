"""The water heater tests for the Tado platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_water_heater_create_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of water heater."""

    await async_init_integration(hass)

    state = hass.states.get("water_heater.water_heater")
    assert state.state == "auto"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_temperature",
        "friendly_name",
        "max_temp",
        "min_temp",
        "operation_list",
        "operation_mode",
        "supported_features",
        "target_temp_high",
        "target_temp_low",
        "temperature",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot

    state = hass.states.get("water_heater.second_water_heater")
    assert state.state == "heat"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_temperature",
        "friendly_name",
        "max_temp",
        "min_temp",
        "operation_list",
        "operation_mode",
        "supported_features",
        "target_temp_high",
        "target_temp_low",
        "temperature",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot
