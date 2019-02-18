"""The tests for the climate component."""
import asyncio

import pytest
import voluptuous as vol

from homeassistant.components.climate import SET_TEMPERATURE_SCHEMA
from tests.common import async_mock_service


@asyncio.coroutine
def test_set_temp_schema_no_req(hass, caplog):
    """Test the set temperature schema with missing required data."""
    domain = 'climate'
    service = 'test_set_temperature'
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {'operation_mode': 'test', 'entity_id': ['climate.test_id']}
    with pytest.raises(vol.Invalid):
        yield from hass.services.async_call(domain, service, data)
    yield from hass.async_block_till_done()

    assert len(calls) == 0


@asyncio.coroutine
def test_set_temp_schema(hass, caplog):
    """Test the set temperature schema with ok required data."""
    domain = 'climate'
    service = 'test_set_temperature'
    schema = SET_TEMPERATURE_SCHEMA
    calls = async_mock_service(hass, domain, service, schema)

    data = {
        'temperature': 20.0, 'operation_mode': 'test',
        'entity_id': ['climate.test_id']}
    yield from hass.services.async_call(domain, service, data)
    yield from hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[-1].data == data
