"""Tests for Vanderbilt SPC alarm control panel platform."""
from homeassistant.components.alarm_control_panel import spc
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_DISARMED)
from homeassistant.components.spc import (DATA_API)


async def test_setup_platform(hass):
    """Test adding areas as separate alarm control panel devices."""
    added_entities = []

    def add_entities(entities):
        nonlocal added_entities
        added_entities = list(entities)

    area_defs = [{
        'id': '1',
        'name': 'House',
        'mode': '3',
        'last_set_time': '1485759851',
        'last_set_user_id': '1',
        'last_set_user_name': 'Pelle',
        'last_unset_time': '1485800564',
        'last_unset_user_id': '1',
        'last_unset_user_name': 'Lisa',
        'last_alarm': '1478174896'
    }, {
        'id': '3',
        'name': 'Garage',
        'mode': '0',
        'last_set_time': '1483705803',
        'last_set_user_id': '9998',
        'last_set_user_name': 'Pelle',
        'last_unset_time': '1483705808',
        'last_unset_user_id': '9998',
        'last_unset_user_name': 'Lisa'
    }]

    from pyspcwebgw import Area

    areas = [Area(gateway=None, spc_area=a) for a in area_defs]

    hass.data[DATA_API] = None

    await spc.async_setup_platform(hass=hass,
                                   config={},
                                   async_add_entities=add_entities,
                                   discovery_info={'areas': areas})

    assert len(added_entities) == 2

    assert added_entities[0].name == 'House'
    assert added_entities[0].state == STATE_ALARM_ARMED_AWAY
    assert added_entities[0].changed_by == 'Pelle'

    assert added_entities[1].name == 'Garage'
    assert added_entities[1].state == STATE_ALARM_DISARMED
    assert added_entities[1].changed_by == 'Lisa'
