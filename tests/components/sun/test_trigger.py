"""The tests for the sun automation."""

from datetime import datetime

from freezegun import freeze_time
import pytest

from homeassistant.components import automation, sun
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service, mock_component


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    mock_component(hass, "group")
    hass.loop.run_until_complete(
        async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})
    )


async def test_sunset_trigger(hass: HomeAssistant, calls) -> None:
    """Test the sunset trigger."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNSET},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"id": "{{ trigger.id}}"},
                    },
                }
            },
        )

        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
            blocking=True,
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(calls) == 0

    with freeze_time(now):
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
            blocking=True,
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["id"] == 0


async def test_sunrise_trigger(hass: HomeAssistant, calls) -> None:
    """Test the sunrise trigger."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNRISE},
                    "action": {"service": "test.automation"},
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(calls) == 1


async def test_sunset_trigger_with_offset(hass: HomeAssistant, calls) -> None:
    """Test the sunset trigger with offset."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNSET,
                        "offset": "0:30:00",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event }}"
                                " - {{ trigger.offset }}"
                            )
                        },
                    },
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(calls) == 1
        assert calls[0].data["some"] == "sun - sunset - 0:30:00"


async def test_sunrise_trigger_with_offset(hass: HomeAssistant, calls) -> None:
    """Test the sunrise trigger with offset."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNRISE,
                        "offset": "-0:30:00",
                    },
                    "action": {"service": "test.automation"},
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(calls) == 1
