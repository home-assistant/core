"""Helpers for hass dispatcher & internal component / platform."""

from homeassistant.core import callback

DATA_DISPATCHER = 'dispatcher'


def dispatcher_connect(hass, signal, target):
    """Connect a callable function to a singal."""
    hass.add_job(async_dispatcher_connect, hass, signal, target)


@callback
def async_dispatcher_connect(hass, signal, target):
    """Connect a callable function to a singal.

    This method must be run in the event loop.
    """
    if DATA_DISPATCHER not in hass.data:
        hass.data[DATA_DISPATCHER] = {}

    if signal not in hass.data[DATA_DISPATCHER]:
        hass.data[DATA_DISPATCHER][signal] = []

    hass.data[DATA_DISPATCHER][signal].append(target)


def dispatcher_send(hass, signal, *args):
    """Send signal and data."""
    hass.add_job(async_dispatcher_send, hass, signal, *args)


@callback
def async_dispatcher_send(hass, signal, *args):
    """Send signal and data.

    This method must be run in the event loop.
    """
    target_list = hass.data.get(DATA_DISPATCHER, {}).get(signal, [])

    for target in target_list:
        hass.async_add_job(target, *args)
