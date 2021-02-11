"""Test the condition helper."""
from logging import ERROR, WARNING
from unittest.mock import patch

import pytest

from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import condition
from homeassistant.helpers.template import Template
from homeassistant.setup import async_setup_component
from homeassistant.util import dt


async def test_invalid_condition(hass):
    """Test if invalid condition raises."""
    with pytest.raises(HomeAssistantError):
        await condition.async_from_config(
            hass,
            {
                "condition": "invalid",
                "conditions": [
                    {
                        "condition": "state",
                        "entity_id": "sensor.temperature",
                        "state": "100",
                    },
                ],
            },
        )


async def test_and_condition(hass):
    """Test the 'and' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 110,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_and_condition_with_template(hass):
    """Test the 'and' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "template",
                    "value_template": '{{ states.sensor.temperature.state == "100" }}',
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 110,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_or_condition(hass):
    """Test the 'or' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "or",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 110,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_or_condition_with_template(hass):
    """Test the 'or' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "or",
            "conditions": [
                {'{{ states.sensor.temperature.state == "100" }}'},
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 110,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 120)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 105)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)


async def test_not_condition(hass):
    """Test the 'not' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "not",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 50,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 101)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 50)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)


async def test_not_condition_with_template(hass):
    """Test the 'or' condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "not",
            "conditions": [
                {
                    "condition": "template",
                    "value_template": '{{ states.sensor.temperature.state == "100" }}',
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": 50,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 101)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 50)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)


async def test_time_window(hass):
    """Test time condition windows."""
    sixam = dt.parse_time("06:00:00")
    sixpm = dt.parse_time("18:00:00")

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=3),
    ):
        assert not condition.time(hass, after=sixam, before=sixpm)
        assert condition.time(hass, after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=9),
    ):
        assert condition.time(hass, after=sixam, before=sixpm)
        assert not condition.time(hass, after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=15),
    ):
        assert condition.time(hass, after=sixam, before=sixpm)
        assert not condition.time(hass, after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=21),
    ):
        assert not condition.time(hass, after=sixam, before=sixpm)
        assert condition.time(hass, after=sixpm, before=sixam)


async def test_time_using_input_datetime(hass):
    """Test time conditions using input_datetime entities."""
    await async_setup_component(
        hass,
        "input_datetime",
        {
            "input_datetime": {
                "am": {"has_date": True, "has_time": True},
                "pm": {"has_date": True, "has_time": True},
            }
        },
    )

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            "entity_id": "input_datetime.am",
            "datetime": str(
                dt.now()
                .replace(hour=6, minute=0, second=0, microsecond=0)
                .replace(tzinfo=None)
            ),
        },
        blocking=True,
    )

    await hass.services.async_call(
        "input_datetime",
        "set_datetime",
        {
            "entity_id": "input_datetime.pm",
            "datetime": str(
                dt.now()
                .replace(hour=18, minute=0, second=0, microsecond=0)
                .replace(tzinfo=None)
            ),
        },
        blocking=True,
    )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=3),
    ):
        assert not condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=9),
    ):
        assert condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert not condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=15),
    ):
        assert condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert not condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=21),
    ):
        assert not condition.time(
            hass, after="input_datetime.am", before="input_datetime.pm"
        )
        assert condition.time(
            hass, after="input_datetime.pm", before="input_datetime.am"
        )

    assert not condition.time(hass, after="input_datetime.not_existing")
    assert not condition.time(hass, before="input_datetime.not_existing")


async def test_if_numeric_state_raises_on_unavailable(hass, caplog):
    """Test numeric_state raises on unavailable/unknown state."""
    test = await condition.async_from_config(
        hass,
        {"condition": "numeric_state", "entity_id": "sensor.temperature", "below": 42},
    )

    caplog.clear()
    caplog.set_level(WARNING)

    hass.states.async_set("sensor.temperature", "unavailable")
    with pytest.raises(ConditionError):
        test(hass)
    assert len(caplog.record_tuples) == 0

    hass.states.async_set("sensor.temperature", "unknown")
    with pytest.raises(ConditionError):
        test(hass)
    assert len(caplog.record_tuples) == 0


async def test_state_raises(hass):
    """Test that state raises ConditionError on errors."""
    # Unknown entity_id
    with pytest.raises(ConditionError, match="Unknown entity"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "state",
                "entity_id": "sensor.door_unknown",
                "state": "open",
            },
        )

        test(hass)

    # Unknown attribute
    with pytest.raises(ConditionError, match=r"Attribute .* does not exist"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "state",
                "entity_id": "sensor.door",
                "attribute": "model",
                "state": "acme",
            },
        )

        hass.states.async_set("sensor.door", "open")
        test(hass)


async def test_state_multiple_entities(hass):
    """Test with multiple entities in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": ["sensor.temperature_1", "sensor.temperature_2"],
                    "state": "100",
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 101)
    hass.states.async_set("sensor.temperature_2", 100)
    assert not test(hass)

    hass.states.async_set("sensor.temperature_1", 100)
    hass.states.async_set("sensor.temperature_2", 101)
    assert not test(hass)


async def test_multiple_states(hass):
    """Test with multiple states in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": ["100", "200"],
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 100)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 200)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 42)
    assert not test(hass)


async def test_state_attribute(hass):
    """Test with state attribute in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "attribute": "attribute1",
                    "state": 200,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 100, {"unkown_attr": 200})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 200})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "200"})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 201})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test(hass)


async def test_state_attribute_boolean(hass):
    """Test with boolean state attribute in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "state",
            "entity_id": "sensor.temperature",
            "attribute": "happening",
            "state": False,
        },
    )

    hass.states.async_set("sensor.temperature", 100, {"happening": 200})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"happening": True})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"no_happening": 201})
    with pytest.raises(ConditionError):
        test(hass)

    hass.states.async_set("sensor.temperature", 100, {"happening": False})
    assert test(hass)


async def test_state_using_input_entities(hass):
    """Test state conditions using input_* entities."""
    await async_setup_component(
        hass,
        "input_text",
        {
            "input_text": {
                "hello": {"initial": "goodbye"},
            }
        },
    )

    await async_setup_component(
        hass,
        "input_select",
        {
            "input_select": {
                "hello": {"options": ["cya", "goodbye", "welcome"], "initial": "cya"},
            }
        },
    )

    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.salut",
                    "state": [
                        "input_text.hello",
                        "input_select.hello",
                        "input_number.not_exist",
                        "salut",
                    ],
                },
            ],
        },
    )

    hass.states.async_set("sensor.salut", "goodbye")
    assert test(hass)

    hass.states.async_set("sensor.salut", "salut")
    assert test(hass)

    hass.states.async_set("sensor.salut", "hello")
    assert not test(hass)

    await hass.services.async_call(
        "input_text",
        "set_value",
        {
            "entity_id": "input_text.hello",
            "value": "hi",
        },
        blocking=True,
    )
    assert not test(hass)

    hass.states.async_set("sensor.salut", "hi")
    assert test(hass)

    hass.states.async_set("sensor.salut", "cya")
    assert test(hass)

    await hass.services.async_call(
        "input_select",
        "select_option",
        {
            "entity_id": "input_select.hello",
            "option": "welcome",
        },
        blocking=True,
    )
    assert not test(hass)

    hass.states.async_set("sensor.salut", "welcome")
    assert test(hass)


async def test_numeric_state_raises(hass):
    """Test that numeric_state raises ConditionError on errors."""
    # Unknown entity_id
    with pytest.raises(ConditionError, match="Unknown entity"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature_unknown",
                "above": 0,
            },
        )

        test(hass)

    # Unknown attribute
    with pytest.raises(ConditionError, match=r"Attribute .* does not exist"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "attribute": "temperature",
                "above": 0,
            },
        )

        hass.states.async_set("sensor.temperature", 50)
        test(hass)

    # Template error
    with pytest.raises(ConditionError, match="ZeroDivisionError"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "value_template": "{{ 1 / 0 }}",
                "above": 0,
            },
        )

        hass.states.async_set("sensor.temperature", 50)
        test(hass)

    # Unavailable state
    with pytest.raises(ConditionError, match="State is not available"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "above": 0,
            },
        )

        hass.states.async_set("sensor.temperature", "unavailable")
        test(hass)

    # Bad number
    with pytest.raises(ConditionError, match="cannot be processed as a number"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "above": 0,
            },
        )

        hass.states.async_set("sensor.temperature", "fifty")
        test(hass)

    # Below entity missing
    with pytest.raises(ConditionError, match="below entity"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "below": "input_number.missing",
            },
        )

        hass.states.async_set("sensor.temperature", 50)
        test(hass)

    # Above entity missing
    with pytest.raises(ConditionError, match="above entity"):
        test = await condition.async_from_config(
            hass,
            {
                "condition": "numeric_state",
                "entity_id": "sensor.temperature",
                "above": "input_number.missing",
            },
        )

        hass.states.async_set("sensor.temperature", 50)
        test(hass)


async def test_numeric_state_multiple_entities(hass):
    """Test with multiple entities in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "numeric_state",
                    "entity_id": ["sensor.temperature_1", "sensor.temperature_2"],
                    "below": 50,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature_1", 49)
    hass.states.async_set("sensor.temperature_2", 49)
    assert test(hass)

    hass.states.async_set("sensor.temperature_1", 50)
    hass.states.async_set("sensor.temperature_2", 49)
    assert not test(hass)

    hass.states.async_set("sensor.temperature_1", 49)
    hass.states.async_set("sensor.temperature_2", 50)
    assert not test(hass)


async def test_numberic_state_attribute(hass):
    """Test with numeric state attribute in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "attribute": "attribute1",
                    "below": 50,
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 100, {"unkown_attr": 10})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 49})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "49"})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 51})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test(hass)


async def test_numeric_state_using_input_number(hass):
    """Test numeric_state conditions using input_number entities."""
    await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "low": {"min": 0, "max": 255, "initial": 10},
                "high": {"min": 0, "max": 255, "initial": 100},
            }
        },
    )

    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature",
                    "below": "input_number.high",
                    "above": "input_number.low",
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 42)
    assert test(hass)

    hass.states.async_set("sensor.temperature", 10)
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100)
    assert not test(hass)

    await hass.services.async_call(
        "input_number",
        "set_value",
        {
            "entity_id": "input_number.high",
            "value": 101,
        },
        blocking=True,
    )
    assert test(hass)

    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", below="input_number.not_exist"
        )
    with pytest.raises(ConditionError):
        condition.async_numeric_state(
            hass, entity="sensor.temperature", above="input_number.not_exist"
        )


async def test_zone_multiple_entities(hass):
    """Test with multiple entities in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "zone",
                    "entity_id": ["device_tracker.person_1", "device_tracker.person_2"],
                    "zone": "zone.home",
                },
            ],
        },
    )

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 20.1, "longitude": 10.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert not test(hass)

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 20.1, "longitude": 10.1},
    )
    assert not test(hass)


async def test_multiple_zones(hass):
    """Test with multiple entities in condition."""
    test = await condition.async_from_config(
        hass,
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "zone",
                    "entity_id": "device_tracker.person",
                    "zone": ["zone.home", "zone.work"],
                },
            ],
        },
    )

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 20.1, "longitude": 10.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 2.1, "longitude": 1.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 20.1, "longitude": 10.1},
    )
    assert test(hass)

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 50.1, "longitude": 20.1},
    )
    assert not test(hass)


async def test_extract_entities():
    """Test extracting entities."""
    assert condition.async_extract_entities(
        {
            "condition": "and",
            "conditions": [
                {
                    "condition": "state",
                    "entity_id": "sensor.temperature",
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": "sensor.temperature_2",
                    "below": 110,
                },
                {
                    "condition": "not",
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "sensor.temperature_3",
                            "state": "100",
                        },
                        {
                            "condition": "numeric_state",
                            "entity_id": "sensor.temperature_4",
                            "below": 110,
                        },
                    ],
                },
                {
                    "condition": "or",
                    "conditions": [
                        {
                            "condition": "state",
                            "entity_id": "sensor.temperature_5",
                            "state": "100",
                        },
                        {
                            "condition": "numeric_state",
                            "entity_id": "sensor.temperature_6",
                            "below": 110,
                        },
                    ],
                },
                {
                    "condition": "state",
                    "entity_id": ["sensor.temperature_7", "sensor.temperature_8"],
                    "state": "100",
                },
                {
                    "condition": "numeric_state",
                    "entity_id": ["sensor.temperature_9", "sensor.temperature_10"],
                    "below": 110,
                },
                Template("{{ is_state('light.example', 'on') }}"),
            ],
        }
    ) == {
        "sensor.temperature",
        "sensor.temperature_2",
        "sensor.temperature_3",
        "sensor.temperature_4",
        "sensor.temperature_5",
        "sensor.temperature_6",
        "sensor.temperature_7",
        "sensor.temperature_8",
        "sensor.temperature_9",
        "sensor.temperature_10",
    }


async def test_extract_devices():
    """Test extracting devices."""
    assert (
        condition.async_extract_devices(
            {
                "condition": "and",
                "conditions": [
                    {"condition": "device", "device_id": "abcd", "domain": "light"},
                    {"condition": "device", "device_id": "qwer", "domain": "switch"},
                    {
                        "condition": "state",
                        "entity_id": "sensor.not_a_device",
                        "state": "100",
                    },
                    {
                        "condition": "not",
                        "conditions": [
                            {
                                "condition": "device",
                                "device_id": "abcd_not",
                                "domain": "light",
                            },
                            {
                                "condition": "device",
                                "device_id": "qwer_not",
                                "domain": "switch",
                            },
                        ],
                    },
                    {
                        "condition": "or",
                        "conditions": [
                            {
                                "condition": "device",
                                "device_id": "abcd_or",
                                "domain": "light",
                            },
                            {
                                "condition": "device",
                                "device_id": "qwer_or",
                                "domain": "switch",
                            },
                        ],
                    },
                    Template("{{ is_state('light.example', 'on') }}"),
                ],
            }
        )
        == {"abcd", "qwer", "abcd_not", "qwer_not", "abcd_or", "qwer_or"}
    )


async def test_condition_template_error(hass, caplog):
    """Test invalid template."""
    caplog.set_level(ERROR)

    test = await condition.async_from_config(
        hass, {"condition": "template", "value_template": "{{ undefined.state }}"}
    )

    assert not test(hass)
    assert len(caplog.records) == 1
    assert caplog.records[0].message.startswith(
        "Error during template condition: UndefinedError:"
    )


async def test_condition_template_invalid_results(hass):
    """Test template condition render false with invalid results."""
    test = await condition.async_from_config(
        hass, {"condition": "template", "value_template": "{{ 'string' }}"}
    )
    assert not test(hass)

    test = await condition.async_from_config(
        hass, {"condition": "template", "value_template": "{{ 10.1 }}"}
    )
    assert not test(hass)

    test = await condition.async_from_config(
        hass, {"condition": "template", "value_template": "{{ 42 }}"}
    )
    assert not test(hass)

    test = await condition.async_from_config(
        hass, {"condition": "template", "value_template": "{{ [1, 2, 3] }}"}
    )
    assert not test(hass)
