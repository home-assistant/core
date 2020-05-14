"""The tests for the litejet component."""
from datetime import timedelta
import logging
from unittest import mock

import pytest

from homeassistant import setup
from homeassistant.components import litejet
import homeassistant.components.automation as automation
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed, async_mock_service

_LOGGER = logging.getLogger(__name__)

ENTITY_SWITCH = "switch.mock_switch_1"
ENTITY_SWITCH_NUMBER = 1
ENTITY_OTHER_SWITCH = "switch.mock_switch_2"
ENTITY_OTHER_SWITCH_NUMBER = 2


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


def get_switch_name(number):
    """Get a mock switch name."""
    return f"Mock Switch #{number}"


@pytest.fixture
def mock_lj(hass):
    """Initialize components."""
    with mock.patch("homeassistant.components.litejet.LiteJet") as mock_pylitejet:
        mock_lj = mock_pylitejet.return_value

        mock_lj.switch_pressed_callbacks = {}
        mock_lj.switch_released_callbacks = {}

        def on_switch_pressed(number, callback):
            mock_lj.switch_pressed_callbacks[number] = callback

        def on_switch_released(number, callback):
            mock_lj.switch_released_callbacks[number] = callback

        mock_lj.loads.return_value = range(0)
        mock_lj.button_switches.return_value = range(1, 3)
        mock_lj.all_switches.return_value = range(1, 6)
        mock_lj.scenes.return_value = range(0)
        mock_lj.get_switch_name.side_effect = get_switch_name
        mock_lj.on_switch_pressed.side_effect = on_switch_pressed
        mock_lj.on_switch_released.side_effect = on_switch_released

        config = {"litejet": {"port": "/dev/serial/by-id/mock-litejet"}}
        assert hass.loop.run_until_complete(
            setup.async_setup_component(hass, litejet.DOMAIN, config)
        )

        mock_lj.start_time = dt_util.utcnow()
        mock_lj.last_delta = timedelta(0)
        return mock_lj


async def simulate_press(hass, mock_lj, number):
    """Test to simulate a press."""
    _LOGGER.info("*** simulate press of %d", number)
    callback = mock_lj.switch_pressed_callbacks.get(number)
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_lj.start_time + mock_lj.last_delta,
    ):
        if callback is not None:
            await hass.async_add_job(callback)
        await hass.async_block_till_done()


async def simulate_release(hass, mock_lj, number):
    """Test to simulate releasing."""
    _LOGGER.info("*** simulate release of %d", number)
    callback = mock_lj.switch_released_callbacks.get(number)
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_lj.start_time + mock_lj.last_delta,
    ):
        if callback is not None:
            await hass.async_add_job(callback)
        await hass.async_block_till_done()


async def simulate_time(hass, mock_lj, delta):
    """Test to simulate time."""
    _LOGGER.info(
        "*** simulate time change by %s: %s", delta, mock_lj.start_time + delta
    )
    mock_lj.last_delta = delta
    with mock.patch(
        "homeassistant.helpers.condition.dt_util.utcnow",
        return_value=mock_lj.start_time + delta,
    ):
        _LOGGER.info("now=%s", dt_util.utcnow())
        async_fire_time_changed(hass, mock_lj.start_time + delta)
        await hass.async_block_till_done()
        _LOGGER.info("done with now=%s", dt_util.utcnow())


async def setup_automation(hass, trigger):
    """Test setting up the automation."""
    assert await setup.async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "My Test",
                    "trigger": trigger,
                    "action": {"service": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()


async def test_simple(hass, calls, mock_lj):
    """Test the simplest form of a LiteJet trigger."""
    await setup_automation(
        hass, {"platform": "litejet", "number": ENTITY_OTHER_SWITCH_NUMBER}
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)

    assert len(calls) == 1


async def test_held_more_than_short(hass, calls, mock_lj):
    """Test a too short hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "200"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_lj, timedelta(seconds=0.1))
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_more_than_long(hass, calls, mock_lj):
    """Test a hold that is long enough."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "200"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_lj, timedelta(seconds=0.3))
    assert len(calls) == 1
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1


async def test_held_less_than_short(hass, calls, mock_lj):
    """Test a hold that is short enough."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_less_than": {"milliseconds": "200"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_lj, timedelta(seconds=0.1))
    assert len(calls) == 0
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1


async def test_held_less_than_long(hass, calls, mock_lj):
    """Test a hold that is too long."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_less_than": {"milliseconds": "200"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_lj, timedelta(seconds=0.3))
    assert len(calls) == 0
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_in_range_short(hass, calls, mock_lj):
    """Test an in-range trigger with a too short hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "100"},
            "held_less_than": {"milliseconds": "300"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    await simulate_time(hass, mock_lj, timedelta(seconds=0.05))
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0


async def test_held_in_range_just_right(hass, calls, mock_lj):
    """Test an in-range trigger with a just right hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "100"},
            "held_less_than": {"milliseconds": "300"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_lj, timedelta(seconds=0.2))
    assert len(calls) == 0
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 1


async def test_held_in_range_long(hass, calls, mock_lj):
    """Test an in-range trigger with a too long hold."""
    await setup_automation(
        hass,
        {
            "platform": "litejet",
            "number": ENTITY_OTHER_SWITCH_NUMBER,
            "held_more_than": {"milliseconds": "100"},
            "held_less_than": {"milliseconds": "300"},
        },
    )

    await simulate_press(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
    await simulate_time(hass, mock_lj, timedelta(seconds=0.4))
    assert len(calls) == 0
    await simulate_release(hass, mock_lj, ENTITY_OTHER_SWITCH_NUMBER)
    assert len(calls) == 0
