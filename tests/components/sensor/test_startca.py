"""Tests for the Start.ca sensor platform."""
import asyncio
from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor.startca import StartcaData
from homeassistant.helpers.aiohttp_client import async_get_clientsession


@asyncio.coroutine
def test_capped_setup(hass, aioclient_mock):
    """Test the default setup."""
    config = {'platform': 'startca',
              'api_key': 'NOTAKEY',
              'total_bandwidth': 400,
              'monitored_variables': [
                  'usage',
                  'usage_gb',
                  'limit',
                  'used_download',
                  'used_upload',
                  'used_total',
                  'grace_download',
                  'grace_upload',
                  'grace_total',
                  'total_download',
                  'total_upload',
                  'used_remaining']}

    result = '<?xml version="1.0" encoding="ISO-8859-15"?>'\
             '<usage>'\
             '<version>1.1</version>'\
             '<total> <!-- total actual usage -->'\
             '<download>304946829777</download>'\
             '<upload>6480700153</upload>'\
             '</total>'\
             '<used> <!-- part of usage that counts against quota -->'\
             '<download>304946829777</download>'\
             '<upload>6480700153</upload>'\
             '</used>'\
             '<grace> <!-- part of usage that is free -->'\
             '<download>304946829777</download>'\
             '<upload>6480700153</upload>'\
             '</grace>'\
             '</usage>'
    aioclient_mock.get('https://www.start.ca/support/usage/api?key='
                       'NOTAKEY',
                       text=result)

    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    state = hass.states.get('sensor.start_ca_usage_ratio')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '76.24'

    state = hass.states.get('sensor.start_ca_usage')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_data_limit')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '400'

    state = hass.states.get('sensor.start_ca_used_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_used_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '6.48'

    state = hass.states.get('sensor.start_ca_used_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '311.43'

    state = hass.states.get('sensor.start_ca_grace_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_grace_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '6.48'

    state = hass.states.get('sensor.start_ca_grace_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '311.43'

    state = hass.states.get('sensor.start_ca_total_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_total_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '6.48'

    state = hass.states.get('sensor.start_ca_remaining')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '95.05'


@asyncio.coroutine
def test_unlimited_setup(hass, aioclient_mock):
    """Test the default setup."""
    config = {'platform': 'startca',
              'api_key': 'NOTAKEY',
              'total_bandwidth': 0,
              'monitored_variables': [
                  'usage',
                  'usage_gb',
                  'limit',
                  'used_download',
                  'used_upload',
                  'used_total',
                  'grace_download',
                  'grace_upload',
                  'grace_total',
                  'total_download',
                  'total_upload',
                  'used_remaining']}

    result = '<?xml version="1.0" encoding="ISO-8859-15"?>'\
             '<usage>'\
             '<version>1.1</version>'\
             '<total> <!-- total actual usage -->'\
             '<download>304946829777</download>'\
             '<upload>6480700153</upload>'\
             '</total>'\
             '<used> <!-- part of usage that counts against quota -->'\
             '<download>0</download>'\
             '<upload>0</upload>'\
             '</used>'\
             '<grace> <!-- part of usage that is free -->'\
             '<download>304946829777</download>'\
             '<upload>6480700153</upload>'\
             '</grace>'\
             '</usage>'
    aioclient_mock.get('https://www.start.ca/support/usage/api?key='
                       'NOTAKEY',
                       text=result)

    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    state = hass.states.get('sensor.start_ca_usage_ratio')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '0'

    state = hass.states.get('sensor.start_ca_usage')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '0.0'

    state = hass.states.get('sensor.start_ca_data_limit')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == 'inf'

    state = hass.states.get('sensor.start_ca_used_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '0.0'

    state = hass.states.get('sensor.start_ca_used_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '0.0'

    state = hass.states.get('sensor.start_ca_used_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '0.0'

    state = hass.states.get('sensor.start_ca_grace_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_grace_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '6.48'

    state = hass.states.get('sensor.start_ca_grace_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '311.43'

    state = hass.states.get('sensor.start_ca_total_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '304.95'

    state = hass.states.get('sensor.start_ca_total_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '6.48'

    state = hass.states.get('sensor.start_ca_remaining')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == 'inf'


@asyncio.coroutine
def test_bad_return_code(hass, aioclient_mock):
    """Test handling a return code that isn't HTTP OK."""
    aioclient_mock.get('https://www.start.ca/support/usage/api?key='
                       'NOTAKEY',
                       status=404)

    scd = StartcaData(hass.loop, async_get_clientsession(hass),
                      'NOTAKEY', 400)

    result = yield from scd.async_update()
    assert result is False


@asyncio.coroutine
def test_bad_json_decode(hass, aioclient_mock):
    """Test decoding invalid json result."""
    aioclient_mock.get('https://www.start.ca/support/usage/api?key='
                       'NOTAKEY',
                       text='this is not xml')

    scd = StartcaData(hass.loop, async_get_clientsession(hass),
                      'NOTAKEY', 400)

    result = yield from scd.async_update()
    assert result is False
