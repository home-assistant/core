"""The tests for the demo calendar component."""
from datetime import timedelta

from homeassistant.bootstrap import async_setup_component
import homeassistant.util.dt as dt_util


async def test_api_calendar_demo_view(hass, aiohttp_client):
    """Test the calendar demo view."""
    await async_setup_component(hass, 'calendar',
                                {'calendar': {'platform': 'demo'}})
    client = await aiohttp_client(hass.http.app)
    response = await client.get(
        '/api/calendar/calendar_2')
    assert response.status == 400
    start = dt_util.now()
    end = start + timedelta(days=1)
    response = await client.get(
        '/api/calendar/calendar_1?start={}&end={}'.format(start.isoformat(),
                                                          end.isoformat()))
    assert response.status == 200
    events = await response.json()
    assert events[0]['summary'] == 'Future Event'
    assert events[0]['title'] == 'Future Event'
