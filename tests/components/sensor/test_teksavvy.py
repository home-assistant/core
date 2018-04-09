"""Tests for the TekSavvy sensor platform."""
import asyncio
from homeassistant.bootstrap import async_setup_component
from homeassistant.components.sensor.teksavvy import TekSavvyData
from homeassistant.helpers.aiohttp_client import async_get_clientsession


@asyncio.coroutine
def test_capped_setup(hass, aioclient_mock):
    """Test the default setup."""
    config = {'platform': 'teksavvy',
              'api_key': 'NOTAKEY',
              'total_bandwidth': 400,
              'monitored_variables': [
                  'usage',
                  'usage_gb',
                  'limit',
                  'onpeak_download',
                  'onpeak_upload',
                  'onpeak_total',
                  'offpeak_download',
                  'offpeak_upload',
                  'offpeak_total',
                  'onpeak_remaining']}

    result = '{"odata.metadata":"http://api.teksavvy.com/web/Usage/$metadata'\
             '#UsageSummaryRecords","value":[{'\
             '"StartDate":"2018-01-01T00:00:00",'\
             '"EndDate":"2018-01-31T00:00:00",'\
             '"OID":"999999","IsCurrent":true,'\
             '"OnPeakDownload":226.75,'\
             '"OnPeakUpload":8.82,'\
             '"OffPeakDownload":36.24,"OffPeakUpload":1.58'\
             '}]}'
    aioclient_mock.get("https://api.teksavvy.com/"
                       "web/Usage/UsageSummaryRecords?"
                       "$filter=IsCurrent%20eq%20true",
                       text=result)

    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    state = hass.states.get('sensor.teksavvy_data_limit')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '400'

    state = hass.states.get('sensor.teksavvy_off_peak_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '36.24'

    state = hass.states.get('sensor.teksavvy_off_peak_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '1.58'

    state = hass.states.get('sensor.teksavvy_off_peak_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '37.82'

    state = hass.states.get('sensor.teksavvy_on_peak_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '226.75'

    state = hass.states.get('sensor.teksavvy_on_peak_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '8.82'

    state = hass.states.get('sensor.teksavvy_on_peak_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '235.57'

    state = hass.states.get('sensor.teksavvy_usage_ratio')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '56.69'

    state = hass.states.get('sensor.teksavvy_usage')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '226.75'

    state = hass.states.get('sensor.teksavvy_remaining')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '173.25'


@asyncio.coroutine
def test_unlimited_setup(hass, aioclient_mock):
    """Test the default setup."""
    config = {'platform': 'teksavvy',
              'api_key': 'NOTAKEY',
              'total_bandwidth': 0,
              'monitored_variables': [
                  'usage',
                  'usage_gb',
                  'limit',
                  'onpeak_download',
                  'onpeak_upload',
                  'onpeak_total',
                  'offpeak_download',
                  'offpeak_upload',
                  'offpeak_total',
                  'onpeak_remaining']}

    result = '{"odata.metadata":"http://api.teksavvy.com/web/Usage/$metadata'\
             '#UsageSummaryRecords","value":[{'\
             '"StartDate":"2018-01-01T00:00:00",'\
             '"EndDate":"2018-01-31T00:00:00",'\
             '"OID":"999999","IsCurrent":true,'\
             '"OnPeakDownload":226.75,'\
             '"OnPeakUpload":8.82,'\
             '"OffPeakDownload":36.24,"OffPeakUpload":1.58'\
             '}]}'
    aioclient_mock.get("https://api.teksavvy.com/"
                       "web/Usage/UsageSummaryRecords?"
                       "$filter=IsCurrent%20eq%20true",
                       text=result)

    yield from async_setup_component(hass, 'sensor', {'sensor': config})

    state = hass.states.get('sensor.teksavvy_data_limit')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == 'inf'

    state = hass.states.get('sensor.teksavvy_off_peak_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '36.24'

    state = hass.states.get('sensor.teksavvy_off_peak_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '1.58'

    state = hass.states.get('sensor.teksavvy_off_peak_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '37.82'

    state = hass.states.get('sensor.teksavvy_on_peak_download')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '226.75'

    state = hass.states.get('sensor.teksavvy_on_peak_upload')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '8.82'

    state = hass.states.get('sensor.teksavvy_on_peak_total')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '235.57'

    state = hass.states.get('sensor.teksavvy_usage')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == '226.75'

    state = hass.states.get('sensor.teksavvy_usage_ratio')
    assert state.attributes.get('unit_of_measurement') == '%'
    assert state.state == '0'

    state = hass.states.get('sensor.teksavvy_remaining')
    assert state.attributes.get('unit_of_measurement') == 'GB'
    assert state.state == 'inf'


@asyncio.coroutine
def test_bad_return_code(hass, aioclient_mock):
    """Test handling a return code that isn't HTTP OK."""
    aioclient_mock.get("https://api.teksavvy.com/"
                       "web/Usage/UsageSummaryRecords?"
                       "$filter=IsCurrent%20eq%20true",
                       status=404)

    tsd = TekSavvyData(hass.loop, async_get_clientsession(hass),
                       'notakey', 400)

    result = yield from tsd.async_update()
    assert result is False


@asyncio.coroutine
def test_bad_json_decode(hass, aioclient_mock):
    """Test decoding invalid json result."""
    aioclient_mock.get("https://api.teksavvy.com/"
                       "web/Usage/UsageSummaryRecords?"
                       "$filter=IsCurrent%20eq%20true",
                       text='this is not json')

    tsd = TekSavvyData(hass.loop, async_get_clientsession(hass),
                       'notakey', 400)

    result = yield from tsd.async_update()
    assert result is False
