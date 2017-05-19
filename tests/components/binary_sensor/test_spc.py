"""Tests for Vanderbilt SPC binary sensor platform."""
import asyncio

import pytest

from homeassistant.components.spc import SpcRegistry
from homeassistant.components.binary_sensor import spc
from tests.common import async_test_home_assistant


@pytest.fixture
def hass(loop):
    """Home Assistant fixture with device mapping registry."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))
    hass.data['spc_registry'] = SpcRegistry()
    yield hass
    loop.run_until_complete(hass.async_stop())


@asyncio.coroutine
def test_setup_platform(hass):
    """Test autodiscovery of supported device types."""
    added_entities = []

    zones = {'devices': [{
        'id': '1',
        'type': '3',
        'zone_name': 'Kitchen smoke',
        'area': '1',
        'area_name': 'House',
        'input': '0',
        'status': '0',
        }, {
        'id': '3',
        'type': '0',
        'zone_name': 'Hallway PIR',
        'area': '1',
        'area_name': 'House',
        'input': '0',
        'status': '0',
        }, {
        'id': '5',
        'type': '1',
        'zone_name': 'Front door',
        'area': '1',
        'area_name': 'House',
        'input': '1',
        'status': '0',
        }]}

    def add_entities(entities):
        nonlocal added_entities
        added_entities = list(entities)

    yield from spc.async_setup_platform(hass=hass,
                                        config={},
                                        async_add_entities=add_entities,
                                        discovery_info=zones)

    assert len(added_entities) == 3
    assert added_entities[0].device_class == 'smoke'
    assert added_entities[0].state == 'off'
    assert added_entities[1].device_class == 'motion'
    assert added_entities[1].state == 'off'
    assert added_entities[2].device_class == 'opening'
    assert added_entities[2].state == 'on'
    assert all(d.hidden for d in added_entities)
