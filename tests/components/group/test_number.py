from __future__ import annotations

import pytest

from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALUES = [17, 20, 15.3]
COUNT = len(VALUES)
MIN_VALUE = min(VALUES)
MAX_VALUE = max(VALUES)
MEAN = sum(VALUES) / COUNT
MEDIAN = sorted(VALUES)[COUNT // 2]
SUM_VALUE = sum(VALUES)
PRODUCT_VALUE = VALUES[0] * VALUES[1] * VALUES[2]
RANGE = max(VALUES) - min(VALUES)
STDEV = (sum((v - MEAN) ** 2 for v in VALUES) / COUNT) ** 0.5


@pytest.mark.parametrize(
    ("number_type", "result"),
    [
        ("min", MIN_VALUE),
        ("max", MAX_VALUE),
        ("mean", MEAN),
        ("median", MEDIAN),
        ("sum", SUM_VALUE),
        ("product", PRODUCT_VALUE),
        ("range", RANGE),
        ("stdev", STDEV),
    ],
)
async def test_numbers(
    hass: HomeAssistant,
    number_type: str,
    result: float,
) -> None:
    config = {
        NUMBER_DOMAIN: {
            "platform": "group",
            "name": "test_group",
            "type": number_type,
            "entities": ["number.test_1", "number.test_2", "number.test_3"],
        }
    }

    entity_ids = config[NUMBER_DOMAIN]["entities"]

    for entity_id, value in dict(zip(entity_ids, VALUES, strict=False)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    assert await async_setup_component(hass, NUMBER_DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get(f"number.test_group")
    assert float(state.state) == pytest.approx(float(result))


async def test_numbers_unavailable(hass: HomeAssistant) -> None:
    config = {
        NUMBER_DOMAIN: {
            "platform": "group",
            "name": "test_max",
            "type": "max",
            "entities": ["number.test_1", "number.test_2", "number.test_3"],
        }
    }

    assert await async_setup_component(hass, NUMBER_DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = config[NUMBER_DOMAIN]["entities"]

    hass.states.async_set(entity_ids[0], STATE_UNKNOWN)
    await hass.async_block_till_done()

    state = hass.states.get("number.test_max")
    assert state.state == STATE_UNAVAILABLE

    hass.states.async_set(entity_ids[1], VALUES[1])
    await hass.async_block_till_done()

    state = hass.states.get("number.test_max")
    assert state.state not in [STATE_UNAVAILABLE, STATE_UNKNOWN]


async def test_set_value_all(hass: HomeAssistant) -> None:
    config = {
        NUMBER_DOMAIN: {
            "platform": "group",
            "name": "test_set_all",
            "type": "mean",
            "entities": ["number.test_1", "number.test_2", "number.test_3"],
            "write_target": "all",
        }
    }

    for eid in config[NUMBER_DOMAIN]["entities"]:
        hass.states.async_set(eid, 0)
    await hass.async_block_till_done()

    assert await async_setup_component(hass, NUMBER_DOMAIN, config)
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        "set_value",
        {"entity_id": "number.test_set_all", "value": 42},
        blocking=True,
    )
    await hass.async_block_till_done()

    for eid in config[NUMBER_DOMAIN]["entities"]:
        state = hass.states.get(eid)
        assert float(state.state) == 42
