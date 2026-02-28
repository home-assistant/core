"""Support for timer triggers."""

from collections.abc import Callable
from typing import Any

import pytest

from homeassistant.components import automation
from homeassistant.components.timer import (
    CONF_DURATION,
    DOMAIN,
    SERVICE_CANCEL,
    SERVICE_FINISH,
    SERVICE_PAUSE,
    SERVICE_START,
)
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service
from tests.components import arm_trigger


@pytest.fixture
def automation_test_calls(hass: HomeAssistant) -> Callable[[], list[dict[str, Any]]]:
    """Fixture to return payload data for automation calls."""
    service_calls = async_mock_service(hass, "test", "automation")

    def get_trigger_data() -> list[dict[str, Any]]:
        return [c.data for c in service_calls]

    return get_trigger_data


async def config_setup(hass: HomeAssistant, triggers: list[str]) -> None:
    """Common initialization for timer and automation."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test": {CONF_DURATION: 10}}}
    )

    automations = [
        {
            "alias": f"test_{trigger}",
            "trigger": {
                "platform": f"{DOMAIN}.{trigger}",
                "target": {
                    "entity_id": "timer.test",
                },
            },
            "action": {
                "service": "test.automation",
                "data_template": {
                    "entity_id": "{{ trigger.data.entity_id }}",
                    "event_type": "{{ trigger.event_type }}",
                    "message": "service called",
                    "id": "{{ trigger.id }}",
                },
            },
        }
        for trigger in triggers
    ]

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {automation.DOMAIN: automations},
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "trigger_key",
    [
        "timer.started",
        "timer.finished",
        "timer.paused",
        "timer.cancelled",
        "timer.restarted",
    ],
)
async def test_timer_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the timer triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("timer", "steps", "timer_event"),
    [
        ("started", [SERVICE_START], "timer.started"),
        ("finished", [SERVICE_START, SERVICE_FINISH], "timer.finished"),
        ("paused", [SERVICE_START, SERVICE_PAUSE], "timer.paused"),
        ("cancelled", [SERVICE_START, SERVICE_CANCEL], "timer.cancelled"),
        ("restarted", [SERVICE_START, SERVICE_PAUSE, SERVICE_START], "timer.restarted"),
        ("restarted", [SERVICE_START, SERVICE_START], "timer.restarted"),
    ],
)
async def test_timer_type_event(
    hass: HomeAssistant, timer, steps, timer_event, automation_test_calls
) -> None:
    """Test timer triggers."""

    await config_setup(hass, [timer])

    for step in steps:
        await hass.services.async_call(
            DOMAIN,
            step,
            {CONF_ENTITY_ID: "timer.test"},
            blocking=True,
        )
        await hass.async_block_till_done()

    test_calls = automation_test_calls()
    assert len(test_calls) == 1
    assert test_calls[0]["entity_id"] == "timer.test"
    assert test_calls[0]["event_type"] == timer_event


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_full_usage(
    hass: HomeAssistant, automation_test_calls, service_calls: list[ServiceCall]
) -> None:
    """Test timer triggers by attaching to all kind of events."""

    await config_setup(
        hass, ["started", "paused", "finished", "cancelled", "restarted"]
    )

    steps = [
        {"call": SERVICE_START},
        {"call": SERVICE_PAUSE},
        {"call": SERVICE_START},
        {"call": SERVICE_CANCEL},
        {"call": SERVICE_START},
        {"call": SERVICE_FINISH},
        {"call": SERVICE_START},
        {"call": SERVICE_START},
    ]
    for index, step in enumerate(steps):
        await hass.services.async_call(
            DOMAIN,
            step["call"],
            {CONF_ENTITY_ID: "timer.test"},
            blocking=True,
        )
        await hass.async_block_till_done()

        test_calls = automation_test_calls()

        assert len(service_calls) == 2 * (index + 1)
        assert len(test_calls) == index + 1
        assert service_calls[2 * index].data["entity_id"] == "timer.test"
        assert test_calls[index]["entity_id"] == "timer.test"


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    "trigger_key",
    [
        DOMAIN,
        "timer.started",
        "timer.finished",
        "timer.paused",
        "timer.cancelled",
        "timer.restarted",
    ],
)
async def test_exception_bad_timer_trigger(
    hass: HomeAssistant, trigger_key, caplog: pytest.LogCaptureFixture
) -> None:
    """Test bad timer configuration."""

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"trigger": {"platform": trigger_key, "oops": "abc123"}},
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert "Unnamed automation could not be validated" in caplog.text
