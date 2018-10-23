"""Test the init file of Mailgun."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components import mailgun

from homeassistant.core import callback


async def test_config_flow_registers_webhook(hass, aiohttp_client):
    """Test setting up Mailgun and sending webhook."""
    with patch('homeassistant.util.get_local_ip', return_value='example.com'):
        result = await hass.config_entries.flow.async_init('mailgun', context={
            'source': 'user'
        })
    assert result['type'] == data_entry_flow.RESULT_TYPE_FORM, result

    result = await hass.config_entries.flow.async_configure(
        result['flow_id'], {})
    assert result['type'] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    webhook_id = result['result'].data['webhook_id']

    mailgun_events = []

    @callback
    def handle_event(event):
        """Handle Mailgun event."""
        mailgun_events.append(event)

    hass.bus.async_listen(mailgun.MESSAGE_RECEIVED, handle_event)

    client = await aiohttp_client(hass.http.app)
    await client.post('/api/webhook/{}'.format(webhook_id), data={
        'hello': 'mailgun'
    })

    assert len(mailgun_events) == 1
    assert mailgun_events[0].data['webhook_id'] == webhook_id
    assert mailgun_events[0].data['hello'] == 'mailgun'
