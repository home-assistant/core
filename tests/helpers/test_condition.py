"""Test the condition helper."""
from logging import ERROR

import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from tests.async_mock import patch


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


async def test_if_numeric_state_not_raise_on_unavailable(hass):
    """Test numeric_state doesn't raise on unavailable/unknown state."""
    test = await condition.async_from_config(
        hass,
        {"condition": "numeric_state", "entity_id": "sensor.temperature", "below": 42},
    )

    with patch("homeassistant.helpers.condition._LOGGER.warning") as logwarn:
        hass.states.async_set("sensor.temperature", "unavailable")
        assert not test(hass)
        assert len(logwarn.mock_calls) == 0

        hass.states.async_set("sensor.temperature", "unknown")
        assert not test(hass)
        assert len(logwarn.mock_calls) == 0


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
                    "state": "200",
                },
            ],
        },
    )

    hass.states.async_set("sensor.temperature", 100, {"unkown_attr": 200})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 200})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": "200"})
    assert test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": 201})
    assert not test(hass)

    hass.states.async_set("sensor.temperature", 100, {"attribute1": None})
    assert not test(hass)


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
