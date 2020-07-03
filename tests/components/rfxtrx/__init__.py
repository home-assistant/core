"""Tests for the rfxtrx component."""
from homeassistant.components import rfxtrx


async def _signal_event(hass, event):
    await hass.async_add_executor_job(rfxtrx.RECEIVED_EVT_SUBSCRIBERS[0], event)
