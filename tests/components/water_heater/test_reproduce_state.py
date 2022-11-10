"""Test reproduce state for Water heater."""
from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    WaterHeaterOperationMode,
)
from homeassistant.core import State
from homeassistant.helpers.state import async_reproduce_state

from tests.common import async_mock_service


async def test_reproducing_states(hass, caplog):
    """Test reproducing Water heater states."""
    hass.states.async_set("water_heater.entity_off", WaterHeaterOperationMode.OFF, {})
    hass.states.async_set(
        "water_heater.entity_on", WaterHeaterOperationMode.ON, {ATTR_TEMPERATURE: 45}
    )
    hass.states.async_set("water_heater.entity_away", WaterHeaterOperationMode.AWAY, {})
    hass.states.async_set(
        "water_heater.entity_boost", WaterHeaterOperationMode.BOOST, {}
    )
    hass.states.async_set(
        "water_heater.entity_all",
        WaterHeaterOperationMode.AWAY,
        {ATTR_PRESET_MODE: "eco", ATTR_TEMPERATURE: 45},
    )

    set_op_calls = async_mock_service(hass, "water_heater", SERVICE_SET_OPERATION_MODE)
    set_temp_calls = async_mock_service(hass, "water_heater", SERVICE_SET_TEMPERATURE)
    set_preset_calls = async_mock_service(hass, "water_heater", SERVICE_SET_PRESET_MODE)

    # These calls should do nothing as entities already in desired state
    await async_reproduce_state(
        hass,
        [
            State("water_heater.entity_off", WaterHeaterOperationMode.OFF),
            State(
                "water_heater.entity_on",
                WaterHeaterOperationMode.ON,
                {ATTR_TEMPERATURE: 45},
            ),
            State("water_heater.entity_away", WaterHeaterOperationMode.AWAY, {}),
            State("water_heater.entity_boost", WaterHeaterOperationMode.BOOST, {}),
            State(
                "water_heater.entity_all",
                WaterHeaterOperationMode.AWAY,
                {ATTR_PRESET_MODE: "eco", ATTR_TEMPERATURE: 45},
            ),
        ],
    )

    assert len(set_op_calls) == 0
    assert len(set_temp_calls) == 0
    assert len(set_preset_calls) == 0

    # Test invalid state is handled
    await async_reproduce_state(
        hass, [State("water_heater.entity_off", "not_supported")]
    )

    assert "not_supported" in caplog.text
    assert len(set_op_calls) == 0
    assert len(set_temp_calls) == 0
    assert len(set_preset_calls) == 0

    # Make sure correct services are called
    await async_reproduce_state(
        hass,
        [
            State(
                "water_heater.entity_off",
                WaterHeaterOperationMode.ON,
                {ATTR_TEMPERATURE: 45},
            ),
            State("water_heater.entity_on", WaterHeaterOperationMode.OFF),
            State(
                "water_heater.entity_away",
                WaterHeaterOperationMode.LEGIONELLA_PREVENTION,
                {},
            ),
            State(
                "water_heater.entity_boost",
                WaterHeaterOperationMode.AWAY,
                {ATTR_TEMPERATURE: 45},
            ),
            State(
                "water_heater.entity_all",
                WaterHeaterOperationMode.ON,
                {ATTR_PRESET_MODE: "normal"},
            ),
            # Should not raise
            State("water_heater.non_existing", "on"),
        ],
    )

    valid_op_calls = [
        {
            "entity_id": "water_heater.entity_off",
            ATTR_OPERATION_MODE: WaterHeaterOperationMode.ON,
        },
        {
            "entity_id": "water_heater.entity_on",
            ATTR_OPERATION_MODE: WaterHeaterOperationMode.OFF,
        },
        {
            "entity_id": "water_heater.entity_away",
            ATTR_OPERATION_MODE: WaterHeaterOperationMode.LEGIONELLA_PREVENTION,
        },
        {
            "entity_id": "water_heater.entity_boost",
            ATTR_OPERATION_MODE: WaterHeaterOperationMode.AWAY,
        },
        {
            "entity_id": "water_heater.entity_all",
            ATTR_OPERATION_MODE: WaterHeaterOperationMode.ON,
        },
    ]
    assert len(set_op_calls) == len(valid_op_calls)
    for call in set_op_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_op_calls
        valid_op_calls.remove(call.data)

    valid_temp_calls = [
        {"entity_id": "water_heater.entity_off", ATTR_TEMPERATURE: 45},
        {"entity_id": "water_heater.entity_boost", ATTR_TEMPERATURE: 45},
    ]
    assert len(set_temp_calls) == len(valid_temp_calls)
    for call in set_temp_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_temp_calls
        valid_temp_calls.remove(call.data)

    valid_preset_calls = [
        {"entity_id": "water_heater.entity_all", ATTR_PRESET_MODE: "normal"},
    ]
    assert len(set_preset_calls) == len(valid_preset_calls)
    for call in set_preset_calls:
        assert call.domain == "water_heater"
        assert call.data in valid_preset_calls
        valid_preset_calls.remove(call.data)
