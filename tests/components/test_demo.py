"""The tests for the Demo component."""
import asyncio
import json
import os

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import demo, device_tracker
from homeassistant.remote import JSONEncoder


@pytest.fixture(autouse=True)
def mock_history(hass):
    """Mock history component loaded."""
    hass.config.components.add('history')


@pytest.fixture
def minimize_demo_platforms(hass):
    """Cleanup demo component for tests."""
    orig = demo.COMPONENTS_WITH_DEMO_PLATFORM
    demo.COMPONENTS_WITH_DEMO_PLATFORM = [
        'switch', 'light', 'media_player']

    yield

    demo.COMPONENTS_WITH_DEMO_PLATFORM = orig


@pytest.fixture(autouse=True)
def demo_cleanup(hass):
    """Clean up device tracker demo file."""
    yield
    try:
        os.remove(hass.config.path(device_tracker.YAML_DEVICES))
    except FileNotFoundError:
        pass


@asyncio.coroutine
def test_if_demo_state_shows_by_default(hass, minimize_demo_platforms):
    """Test if demo state shows if we give no configuration."""
    yield from async_setup_component(hass, demo.DOMAIN, {demo.DOMAIN: {}})

    assert hass.states.get('a.Demo_Mode') is not None


@asyncio.coroutine
def test_hiding_demo_state(hass, minimize_demo_platforms):
    """Test if you can hide the demo card."""
    yield from async_setup_component(hass, demo.DOMAIN, {
        demo.DOMAIN: {'hide_demo_state': 1}})

    assert hass.states.get('a.Demo_Mode') is None


@asyncio.coroutine
def test_all_entities_can_be_loaded_over_json(hass):
    """Test if you can hide the demo card."""
    yield from async_setup_component(hass, demo.DOMAIN, {
        demo.DOMAIN: {'hide_demo_state': 1}})

    try:
        json.dumps(hass.states.async_all(), cls=JSONEncoder)
    except Exception:
        pytest.fail('Unable to convert all demo entities to JSON. '
                    'Wrong data in state machine!')
