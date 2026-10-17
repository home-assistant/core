"""Regression tests for script condition checker cache lifetime."""

import asyncio

import pytest

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script import Script

from tests.common import async_capture_events

TEMPLATE = "{{ (target_percentage | float - current_percentage | float) | abs >= 2 }}"


@pytest.mark.parametrize(
    "condition_config",
    [
        pytest.param(
            {"condition": "template", "value_template": TEMPLATE}, id="direct"
        ),
        pytest.param(
            {
                "condition": "and",
                "conditions": [
                    {"condition": "template", "value_template": TEMPLATE},
                    {
                        "condition": "or",
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": "{{ enabled }}",
                            },
                            {"condition": "template", "value_template": "{{ false }}"},
                        ],
                    },
                ],
            },
            id="nested",
        ),
    ],
)
async def test_condition_cache_stable_across_renders(
    hass: HomeAssistant, condition_config: dict
) -> None:
    """Rendering and changing variables must not create new cached checkers."""
    events = async_capture_events(hass, "condition_cache_passed")
    script = Script(
        hass,
        cv.SCRIPT_SCHEMA([condition_config, {"event": "condition_cache_passed"}]),
        "cache regression",
        "script",
    )
    for target, current in [(33, 30), (31, 30), (27, 30)] * 3:
        before = len(events)
        await script.async_run(
            {
                "target_percentage": target,
                "current_percentage": current,
                "enabled": True,
            },
            Context(),
        )
        await hass.async_block_till_done()
        assert len(events) - before == int(abs(target - current) >= 2)
    assert len(script._condition_cache) == 1
    script._async_unload()
    assert not script._condition_cache


async def test_condition_cache_distinct_templates(hass: HomeAssistant) -> None:
    """Different configurations must not share a checker or its result."""
    events = async_capture_events(hass, "condition_cache_passed")
    script = Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"condition": "template", "value_template": "{{ value >= 2 }}"},
                {"condition": "template", "value_template": "{{ value <= 4 }}"},
                {"event": "condition_cache_passed"},
            ]
        ),
        "distinct conditions",
        "script",
    )
    for value, expected in [(3, 1), (5, 0), (1, 0), (4, 1)] * 3:
        before = len(events)
        await script.async_run({"value": value}, Context())
        await hass.async_block_till_done()
        assert len(events) - before == expected
    assert len(script._condition_cache) == 2
    await script.async_unload()
    assert not script._condition_cache


@pytest.mark.parametrize(
    "warmup", [pytest.param(0, id="cold"), pytest.param(1, id="warm")]
)
async def test_condition_cache_parallel_runs(hass: HomeAssistant, warmup: int) -> None:
    """Parallel runs share prepared conditions, not rendered results."""
    events = async_capture_events(hass, "condition_cache_passed")
    script = Script(
        hass,
        cv.SCRIPT_SCHEMA(
            [
                {"delay": {"milliseconds": 1}},
                {"condition": "template", "value_template": "{{ enabled }}"},
                {"condition": "template", "value_template": "{{ enabled }}"},
                {"event": "condition_cache_passed"},
            ]
        ),
        "parallel conditions",
        "script",
        script_mode="parallel",
    )
    for _ in range(warmup):
        await script.async_run({"enabled": True}, Context())
    await hass.async_block_till_done()
    events.clear()
    for _ in range(3):
        await asyncio.gather(
            *(
                script.async_run({"enabled": enabled}, Context())
                for enabled in [True, False] * 3
            )
        )
        await hass.async_block_till_done()
    assert len(events) == 9
    assert len(script._condition_cache) == 2
    await script.async_unload()
    assert not script._condition_cache
    assert not script.is_running
