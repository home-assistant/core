"""Tests for the rfxtrx component."""
from homeassistant.components import rfxtrx


async def _signal_event(hass, packet_id):
    event = rfxtrx.get_rfx_object(packet_id)

    await hass.async_add_executor_job(
        hass.data[rfxtrx.DOMAIN][rfxtrx.DATA_RFXOBJECT].event_callback, event,
    )

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    return event
