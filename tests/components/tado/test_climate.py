"""The sensor tests for the Tado platform."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .util import async_init_integration


async def test_air_con(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test creation of aircon climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning")
    assert state.state == "cool"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_humidity",
        "current_temperature",
        "fan_mode",
        "fan_modes",
        "friendly_name",
        "hvac_action",
        "hvac_modes",
        "max_temp",
        "min_temp",
        "preset_mode",
        "preset_modes",
        "supported_features",
        "target_temp_step",
        "temperature",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot


async def test_heater(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test creation of heater climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.baseboard_heater")
    assert state.state == "heat"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_humidity",
        "current_temperature",
        "friendly_name",
        "hvac_action",
        "hvac_modes",
        "max_temp",
        "min_temp",
        "preset_mode",
        "preset_modes",
        "supported_features",
        "target_temp_step",
        "temperature",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot


async def test_smartac_with_swing(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of smart ac with swing climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning_with_swing")
    assert state.state == "auto"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_humidity",
        "current_temperature",
        "fan_mode",
        "fan_modes",
        "friendly_name",
        "hvac_action",
        "hvac_modes",
        "max_temp",
        "min_temp",
        "preset_mode",
        "preset_modes",
        "supported_features",
        "target_temp_step",
        "temperature",
        "swing_modes",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot


async def test_smartac_with_fanlevel_vertical_and_horizontal_swing(
    hass: HomeAssistant, snapshot: SnapshotAssertion
) -> None:
    """Test creation of smart ac with swing climate."""

    await async_init_integration(hass)

    state = hass.states.get("climate.air_conditioning_with_fanlevel")
    assert state.state == "heat"

    # Only test for a subset of attributes in case
    # HA changes the implementation and a new one appears
    expected_keys = [
        "current_humidity",
        "current_temperature",
        "fan_mode",
        "fan_modes",
        "friendly_name",
        "hvac_action",
        "hvac_modes",
        "max_temp",
        "min_temp",
        "preset_mode",
        "preset_modes",
        "supported_features",
        "target_temp_step",
        "temperature",
        "swing_modes",
    ]

    actual_attributes_subset = {key: state.attributes.get(key) for key in expected_keys}
    assert actual_attributes_subset == snapshot
