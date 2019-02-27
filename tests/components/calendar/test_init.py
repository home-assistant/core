"""The tests for the calendar component."""
from datetime import timedelta, datetime

from homeassistant.bootstrap import async_setup_component
from homeassistant.const import CONF_MAXIMUM
from homeassistant.components.calendar import DOMAIN
from homeassistant.components.websocket_api.const import TYPE_RESULT
import homeassistant.util.dt as dt_util


async def test_events_http_api(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, DOMAIN,
                                {DOMAIN: {'platform': 'demo'}})
    client = await hass_client()
    response = await client.get(
        '/api/calendars/calendar.calendar_2')
    assert response.status == 400
    start = dt_util.now()
    end = start + timedelta(days=1)
    response = await client.get(
        '/api/calendars/calendar.calendar_1?start={}&end={}'.format(
            start.isoformat(), end.isoformat()))
    assert response.status == 200
    events = await response.json()
    assert events[0]['summary'] == 'Future Event'
    assert events[0]['title'] == 'Future Event'


async def test_calendars_http_api(hass, hass_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, DOMAIN,
                                {DOMAIN: {'platform': 'demo'}})
    client = await hass_client()
    response = await client.get('/api/calendars')
    assert response.status == 200
    data = await response.json()
    assert data == [
        {'entity_id': 'calendar.calendar_1', 'name': 'Calendar 1'},
        {'entity_id': 'calendar.calendar_2', 'name': 'Calendar 2'}
    ]


async def test_websocket_get_events_none_found(hass,
                                               hass_ws_client,
                                               calendar_setup):
    """Test websocket endpoint for getting no events found."""
    client = await hass_ws_client(hass)

    await client.send_json({
        'id': 5,
        'entity_id': 'calendar.fake_calendar',
        'type': 'calendar/events',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert not msg['success']
    assert msg['error']['message'] == 'Entity not found'


async def test_websocket_get_all_events(hass,
                                        hass_ws_client,
                                        calendar_setup):
    """Test websocket endpoint for getting all events no filters."""
    client = await hass_ws_client(hass)

    await client.send_json({
        'id': 5,
        'entity_id': 'calendar.real_calendar',
        'type': 'calendar/events',
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert len(msg['result']) == 3


async def test_websocket_get_todays_events(hass,
                                           hass_ws_client,
                                           calendar_setup):
    """Test websocket endpoint for getting event filter start/end."""
    client = await hass_ws_client(hass)
    today = datetime.today()

    await client.send_json({
        'id': 5,
        'entity_id': 'calendar.real_calendar',
        'type': 'calendar/events',
        'start': today.isoformat(),
        'end': today.isoformat()
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert len(msg['result']) == 1


async def test_websocket_get_max_events(hass,
                                        hass_ws_client,
                                        calendar_setup):
    """Test websocket endpoint for getting event filter start/end."""
    client = await hass_ws_client(hass)
    max_events = 2

    await client.send_json({
        'id': 5,
        'entity_id': 'calendar.real_calendar',
        'type': 'calendar/events',
        CONF_MAXIMUM: max_events
    })

    msg = await client.receive_json()

    assert msg['id'] == 5
    assert msg['type'] == TYPE_RESULT
    assert msg['success']
    assert len(msg['result']) == max_events
