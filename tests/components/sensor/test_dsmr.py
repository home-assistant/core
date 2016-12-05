"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause Entity
to be updated with new values.
"""

import asyncio
from decimal import Decimal
from unittest.mock import Mock

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor.dsmr import DerivativeDSMREntity
from homeassistant.const import STATE_UNKNOWN
from tests.common import assert_setup_component


@asyncio.coroutine
def test_default_setup(hass, monkeypatch):
    """Test the default setup."""
    from dsmr_parser.obis_references import (
        CURRENT_ELECTRICITY_USAGE,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject

    config = {'platform': 'dsmr'}

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject([
            {'value': Decimal('0.1'), 'unit': 'kWh'}
        ]),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([
            {'value': '0001', 'unit': ''}
        ]),
    }

    # mock for injecting DSMR telegram
    dsmr = Mock(return_value=Mock())
    monkeypatch.setattr('dsmr_parser.protocol.create_dsmr_reader', dsmr)

    with assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor',
                                         {'sensor': config})

    telegram_callback = dsmr.call_args_list[0][0][2]

    # make sure entities have been created and return 'unknown' state
    power_consumption = hass.states.get('sensor.power_consumption')
    assert power_consumption.state == 'unknown'
    assert power_consumption.attributes.get('unit_of_measurement') is None

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to update
    yield from asyncio.sleep(0, loop=hass.loop)

    # ensure entities have new state value after incoming telegram
    power_consumption = hass.states.get('sensor.power_consumption')
    assert power_consumption.state == '0.1'
    assert power_consumption.attributes.get('unit_of_measurement') is 'kWh'

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get('sensor.power_tariff')
    assert power_tariff.state == 'low'
    assert power_tariff.attributes.get('unit_of_measurement') is None


def test_derivative():
    """Test calculation of derivative value."""
    from dsmr_parser.objects import MBusObject

    entity = DerivativeDSMREntity('test', '1.0.0')
    yield from entity.async_update()

    assert entity.state == STATE_UNKNOWN, 'initial state not unknown'

    entity.telegram = {
        '1.0.0': MBusObject([
            {'value': 1},
            {'value': 1, 'unit': 'm3'},
        ])
    }
    yield from entity.async_update()

    assert entity.state == STATE_UNKNOWN, \
        'state after first update shoudl still be unknown'

    entity.telegram = {
        '1.0.0': MBusObject([
            {'value': 2},
            {'value': 2, 'unit': 'm3'},
        ])
    }
    yield from entity.async_update()

    assert entity.state == 1, \
        'state should be difference between first and second update'

    assert entity.unit_of_measurement == 'm3/h'
