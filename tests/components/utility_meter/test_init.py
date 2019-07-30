"""The tests for the utility_meter component."""
import logging

from datetime import timedelta
from unittest.mock import patch

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, ATTR_ENTITY_ID)
from homeassistant.components.utility_meter.const import (
    SERVICE_RESET, SERVICE_SELECT_TARIFF, SERVICE_SELECT_NEXT_TARIFF,
    ATTR_TARIFF)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN

_LOGGER = logging.getLogger(__name__)


async def test_services(hass):
    """Test energy sensor reset service."""
    config = {
        'utility_meter': {
            'energy_bill': {
                'source': 'sensor.energy',
                'cycle': 'hourly',
                'tariffs': ['peak', 'offpeak'],
            }
        }
    }

    assert await async_setup_component(hass, DOMAIN, config)
    assert await async_setup_component(hass, SENSOR_DOMAIN, config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    entity_id = config[DOMAIN]['energy_bill']['source']
    hass.states.async_set(entity_id, 1, {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 3, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_peak')
    assert state.state == '2'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state.state == '0'

    # Next tariff
    data = {ATTR_ENTITY_ID: 'utility_meter.energy_bill'}
    await hass.services.async_call(DOMAIN,
                                   SERVICE_SELECT_NEXT_TARIFF, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 4, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_peak')
    assert state.state == '2'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state.state == '1'

    # Change tariff
    data = {ATTR_ENTITY_ID: 'utility_meter.energy_bill',
            ATTR_TARIFF: 'peak'}
    await hass.services.async_call(DOMAIN,
                                   SERVICE_SELECT_TARIFF, data)
    await hass.async_block_till_done()

    now += timedelta(seconds=10)
    with patch('homeassistant.util.dt.utcnow',
               return_value=now):
        hass.states.async_set(entity_id, 5, {"unit_of_measurement": "kWh"},
                              force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_peak')
    assert state.state == '3'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state.state == '1'

    # Reset meters
    data = {ATTR_ENTITY_ID: 'utility_meter.energy_bill'}
    await hass.services.async_call(DOMAIN, SERVICE_RESET, data)
    await hass.async_block_till_done()

    state = hass.states.get('sensor.energy_bill_peak')
    assert state.state == '0'

    state = hass.states.get('sensor.energy_bill_offpeak')
    assert state.state == '0'
