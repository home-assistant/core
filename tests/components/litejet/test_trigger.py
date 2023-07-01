"""The tests for the litejet component."""
from datetime import timedelta
import logging
from unittest import mock
from unittest.mock import patch

import pytest

from homeassistant import setup
import homeassistant.components.automation as automation
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from . import async_init_integration

from tests.common import async_fire_time_changed_exact, async_mock_service


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


_LOGGER = logging.getLogger(__name__)

ENTITY_SWITCH = "switch.mock_switch_1"
ENTITY_SWITCH_NUMBER = 1
ENTITY_OTHER_SWITCH = "switch.mock_switch_2"
ENTITY_OTHER_SWITCH_NUMBER = 2


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def simulate_press(hass, mock_litejet, number):
    """Test to simulate a press."""
    _LOGGER.info("*** simulate press of %d", number)
    callback = mock_litejet.switch_pressed_callbacks.get(number)
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_litejet.start_time + mock_litejet.last_delta,
    ):
        if callback is not None:
            await hass.async_add_executor_job(callback)
        await hass.async_block_till_done()


async def simulate_release(hass, mock_litejet, number):
    """Test to simulate releasing."""
    _LOGGER.info("*** simulate release of %d", number)
    callback = mock_litejet.switch_released_callbacks.get(number)
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_litejet.start_time + mock_litejet.last_delta,
    ):
        if callback is not None:
            await hass.async_add_executor_job(callback)
        await hass.async_block_till_done()


async def simulate_time(hass, mock_litejet, delta):
    """Test to simulate time."""
    _LOGGER.info(
        "*** simulate time change by %s: %s", delta, mock_litejet.start_time + delta
    )
    mock_litejet.last_delta = delta
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_litejet.start_time + delta,
    ):
        _LOGGER.info("now=%s", dt_util.utcnow())
        async_fire_time_changed_exact(hass, mock_litejet.start_time + delta)
        await hass.async_block_till_done()
        _LOGGER.info("done with now=%s", dt_util.utcnow())


async def setup_automation(hass, trigger):
    """Test setting up the automation."""
    await async_init_integration(hass, use_switch=True)
    assert await setup.async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "My Test",
                    "trigger": trigger,
                    "action": {
                        "service": "test.automation",
                        "data_template": {"id": "{{ trigger.id}}"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()


async def test_simple(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test the simplest form of a LiteJet trigger."""
    await setup_automation(
        hass, {"platform": "litejet", "number": ENTITY_OTHER_SWITCH_NUMBER}
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)

    assert len(calls) == 1
    assert calls[0].data["id"] == 0


async def test_only_release(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test the simplest form of a LiteJet trigger."""
    await setup_automation(
        hass, {"platform": "litejet", "number": ENTITY_OTHER_SWITCH_NUMBER}
    )

    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)

    assert len(calls) == 0


async def test_held_more_than_short(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test a too short hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "2000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_litejet, timedelta(seconds=1))
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_more_than_long(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test a hold that is long enough."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "2000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=3))
    assert len(calls) == 1
    assert calls[0].data["id"] == 0
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1


async def test_held_less_than_short(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test a hold that is short enough."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_less_than": {"milliseconds": "2000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_litejet, timedelta(seconds=1))
    assert len(calls) == 0
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


async def test_held_less_than_long(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test a hold that is too long."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_less_than": {"milliseconds": "2000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=3))
    assert len(calls) == 0
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_in_range_short(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test an in-range trigger with a too short hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "1000"},
            "held_less_than": {"milliseconds": "3000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_litejet, timedelta(seconds=0.5))
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_in_range_just_right(
    hass: HomeAssistant, calls, mock_litejet
) -> None:
    """Test an in-range trigger with a just right hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "1000"},
            "held_less_than": {"milliseconds": "3000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=2))
    assert len(calls) == 0
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


async def test_held_in_range_long(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test an in-range trigger with a too long hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "1000"},
            "held_less_than": {"milliseconds": "3000"},
        },
    )

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=4))
    assert len(calls) == 0
    await simulate_release(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_reload(hass: HomeAssistant, calls, mock_litejet) -> None:
    """Test reloading automation."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "1000"},
            "held_less_than": {"milliseconds": "3000"},
        },
    )

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            "automation": {
                "trigger": {
                    "platform": "litejet",
                    "number": ENTITY_OTHER_SWITCH_NUMBER,
                    "held_more_than": {"milliseconds": "10000"},
                },
                "action": {"service": "test.automation"},
            }
        },
    ):
        await hass.services.async_call(
            "automation",
            "reload",
            blocking=True,
        )
        await hass.async_block_till_done()

    await simulate_press(hass, mock_litejet, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=5))
    assert len(calls) == 0
    await simulate_time(hass, mock_litejet, timedelta(seconds=12.5))
    assert len(calls) == 1
