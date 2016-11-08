"""Test for DSMR components."""

import asyncio
from homeassistant.bootstrap import async_setup_component
from unittest.mock import patch
from tests.common import assert_setup_component
from decimal import Decimal


@asyncio.coroutine
def test_default_setup(hass):
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

    with patch('homeassistant.components.sensor.dsmr.DSMR.read_telegram',
               return_value=telegram), assert_setup_component(1):
        yield from async_setup_component(hass, 'sensor', {'sensor': config})

    state = hass.states.get('sensor.power_usage')

    assert state.state == '0.1'
    assert state.attributes.get('unit_of_measurement') is 'kWh'

    state = hass.states.get('sensor.power_tariff')

    assert state.state == 'low'
    assert state.attributes.get('unit_of_measurement') is None
