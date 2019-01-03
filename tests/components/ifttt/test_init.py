"""Test the init file of IFTTT."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.core import callback
from homeassistant.components import ifttt


async def test_config_flow_registers_webhook(hass, aiohttp_client):
    """Test setting up IFTTT and sending webhook."""
    with patch('homeassistant.util.get_local_ip', return_value='example.com'):
        result = await hass.config_entries.flow.async_init('ifttt', context={
            'source': 'user'
        })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    webhook_id = result['result'].data['webhook_id']

    ifttt_events = []

    @callback
    def handle_event(event):
        """Handle IFTTT event."""
        ifttt_events.append(event)

    hass.bus.async_listen(ifttt.EVENT_RECEIVED, handle_event)

    client = await aiohttp_client(hass.http.app)
    await client.post('/api/webhook/{}'.format(webhook_id), json={
        'hello': 'ifttt'
    })

    assert len(ifttt_events) == 1
    assert ifttt_events[0].data['webhook_id'] == webhook_id
    assert ifttt_events[0].data['hello'] == 'ifttt'
