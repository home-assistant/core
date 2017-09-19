"""Tests for Vanderbilt SPC alarm control panel platform."""
import asyncio

import pytest

from homeassistant.components.spc import SpcRegistry
from homeassistant.components.alarm_control_panel import spc
from tests.common import async_test_home_assistant
from homeassistant.const import (
        STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED)


@pytest.fixture
def hass(loop):
    """Home Assistant fixture with device mapping registry."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))
    hass.data['spc_registry'] = SpcRegistry()
    hass.data['spc_api'] = None
    yield hass
    loop.run_until_complete(hass.async_stop())


@asyncio.coroutine
def test_setup_platform(hass):
    """Test adding areas as separate alarm control panel devices."""
    added_entities = []

    def add_entities(entities):
        nonlocal added_entities
        added_entities = list(entities)

    areas = {'areas': [{
        'id': '1',
        'name': 'House',
        'mode': '3',
        'last_set_time': '1485759851',
        'last_set_user_id': '1',
        'last_set_user_name': 'Pelle',
        'last_unset_time': '1485800564',
        'last_unset_user_id': '1',
        'last_unset_user_name': 'Pelle',
        'last_alarm': '1478174896'
        }, {
        'id': '3',
        'name': 'Garage',
        'mode': '0',
        'last_set_time': '1483705803',
        'last_set_user_id': '9998',
        'last_set_user_name': 'Lisa',
        'last_unset_time': '1483705808',
        'last_unset_user_id': '9998',
        'last_unset_user_name': 'Lisa'
        }]}

    yield from spc.async_setup_platform(hass=hass,
                                        config={},
                                        async_add_entities=add_entities,
                                        discovery_info=areas)

    assert len(added_entities) == 2
    assert added_entities[0].name == 'House'
    assert added_entities[0].state == STATE_ALARM_ARMED_AWAY
    assert added_entities[1].name == 'Garage'
    assert added_entities[1].state == STATE_ALARM_DISARMED
