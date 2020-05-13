"""Test the condition helper."""
import pytest

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition
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
        assert not condition.time(after=sixam, before=sixpm)
        assert condition.time(after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=9),
    ):
        assert condition.time(after=sixam, before=sixpm)
        assert not condition.time(after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=15),
    ):
        assert condition.time(after=sixam, before=sixpm)
        assert not condition.time(after=sixpm, before=sixam)

    with patch(
        "homeassistant.helpers.condition.dt_util.now",
        return_value=dt.now().replace(hour=21),
    ):
        assert not condition.time(after=sixam, before=sixpm)
        assert condition.time(after=sixpm, before=sixam)


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
            ],
        }
    ) == {
        "sensor.temperature",
        "sensor.temperature_2",
        "sensor.temperature_3",
        "sensor.temperature_4",
        "sensor.temperature_5",
        "sensor.temperature_6",
    }


async def test_extract_devices():
    """Test extracting devices."""
    assert condition.async_extract_devices(
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
    ) == {"abcd", "qwer", "abcd_not", "qwer_not", "abcd_or", "qwer_or"}
