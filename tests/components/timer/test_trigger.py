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


@pytest.fixture
def automation_test_calls(hass: HomeAssistant) -> Callable[[], list[dict[str, Any]]]:
    """Fixture to return payload data for automation calls."""
    service_calls = async_mock_service(hass, "test", "automation")

    def get_trigger_data() -> list[dict[str, Any]]:
        return [c.data for c in service_calls]

    return get_trigger_data


async def config_setup(hass: HomeAssistant, events: list[str]) -> None:
    """Common initialization for timer and automation."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"test": {CONF_DURATION: 10}}}
    )
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "test",
                    "trigger": {
                        "platform": f"{DOMAIN}.events",
                        "target": {
                            "entity_id": "timer.test",
                        },
                        "options": {
                            "events": events,
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
            ]
        },
    )
    await hass.async_block_till_done()


async def test_triggers(
    hass: HomeAssistant, automation_test_calls, service_calls: list[ServiceCall]
) -> None:
    """Test timer triggers."""

    await config_setup(hass, ["start", "pause", "finish", "restart", "cancel"])

    steps = [
        {"call": SERVICE_START},
        {"call": SERVICE_PAUSE},
        {"call": SERVICE_START},
        {"call": SERVICE_CANCEL},
        {"call": SERVICE_START},
        {"call": SERVICE_FINISH},
        {"call": SERVICE_START},
        {"call": SERVICE_START},  # restart event
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


async def test_restart_event(hass: HomeAssistant, automation_test_calls) -> None:
    """Test timer triggers."""

    await config_setup(hass, ["restart"])

    steps = [
        {"call": SERVICE_START},
        {"call": SERVICE_START},  # restart event
    ]
    for step in steps:
        await hass.services.async_call(
            DOMAIN,
            step["call"],
            {CONF_ENTITY_ID: "timer.test"},
            blocking=True,
        )
        await hass.async_block_till_done()

    test_calls = automation_test_calls()
    assert len(test_calls) == 1
    assert test_calls[0]["entity_id"] == "timer.test"
    assert test_calls[0]["event_type"] == "timer.restarted"


async def test_exception_bad_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for exception on event triggers firing."""

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"trigger": {"platform": DOMAIN, "oops": "abc123"}},
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
