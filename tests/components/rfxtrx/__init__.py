"""Tests for the rfxtrx component."""
from homeassistant.components import rfxtrx


async def _signal_event(hass, packet_id):
    event = rfxtrx.get_rfx_object(packet_id)
    hass.helpers.dispatcher.async_dispatcher_send(rfxtrx.SIGNAL_EVENT, event)
    await hass.async_block_till_done()
    return event
