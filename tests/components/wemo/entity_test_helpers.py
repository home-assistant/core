"""Test cases that are in common among wemo platform modules.

This is not a test module. These test methods are used by the platform test modules.
"""
import asyncio
import threading
from unittest.mock import patch

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.setup import async_setup_component


def _perform_registry_callback(hass, pywemo_registry, pywemo_device):
    """Return a callable method to trigger a state callback from the device."""

    @callback
    def async_callback():
        # Cause a state update callback to be triggered by the device.
        pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
        return hass.async_block_till_done()

    return async_callback


def _perform_async_update(hass, wemo_entity):
    """Return a callable method to cause hass to update the state of the entity."""

    @callback
    def async_callback():
        return hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )

    return async_callback


async def _async_multiple_call_helper(
    hass,
    pywemo_registry,
    wemo_entity,
    pywemo_device,
    call1,
    call2,
    update_polling_method=None,
):
    """Create two calls (call1 & call2) in parallel; verify only one polls the device.

    The platform entity should only perform one update poll on the device at a time.
    Any parallel updates that happen at the same time should be ignored. This is
    verified by blocking in the update polling method. The polling method should
    only be called once as a result of calling call1 & call2 simultaneously.
    """
    # get_state is called outside the event loop. Use non-async Python Event.
    event = threading.Event()

    def get_update(force_update=True):
        event.wait()

    update_polling_method = update_polling_method or pywemo_device.get_state
    update_polling_method.side_effect = get_update

    # One of these two calls will block on `event`. The other will return right
    # away because the `_update_lock` is held.
    _, pending = await asyncio.wait(
        [call1(), call2()], return_when=asyncio.FIRST_COMPLETED
    )

    # Allow the blocked call to return.
    event.set()
    if pending:
        await asyncio.wait(pending)

    # Make sure the state update only happened once.
    update_polling_method.assert_called_once()


async def test_async_update_locked_callback_and_update(
    hass, pywemo_registry, wemo_entity, pywemo_device, **kwargs
):
    """Test that a callback and a state update request can't both happen at the same time.

    When a state update is received via a callback from the device at the same time
    as hass is calling `async_update`, verify that only one of the updates proceeds.
    """
    await async_setup_component(hass, HA_DOMAIN, {})
    callback = _perform_registry_callback(hass, pywemo_registry, pywemo_device)
    update = _perform_async_update(hass, wemo_entity)
    await _async_multiple_call_helper(
        hass, pywemo_registry, wemo_entity, pywemo_device, callback, update, **kwargs
    )


async def test_async_update_locked_multiple_updates(
    hass, pywemo_registry, wemo_entity, pywemo_device, **kwargs
):
    """Test that two hass async_update state updates do not proceed at the same time."""
    await async_setup_component(hass, HA_DOMAIN, {})
    update = _perform_async_update(hass, wemo_entity)
    await _async_multiple_call_helper(
        hass, pywemo_registry, wemo_entity, pywemo_device, update, update, **kwargs
    )


async def test_async_update_locked_multiple_callbacks(
    hass, pywemo_registry, wemo_entity, pywemo_device, **kwargs
):
    """Test that two device callback state updates do not proceed at the same time."""
    await async_setup_component(hass, HA_DOMAIN, {})
    callback = _perform_registry_callback(hass, pywemo_registry, pywemo_device)
    await _async_multiple_call_helper(
        hass, pywemo_registry, wemo_entity, pywemo_device, callback, callback, **kwargs
    )


async def test_async_locked_update_with_exception(
    hass, wemo_entity, pywemo_device, update_polling_method=None
):
    """Test that the entity becomes unavailable when communication is lost."""
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
    await async_setup_component(hass, HA_DOMAIN, {})
    update_polling_method = update_polling_method or pywemo_device.get_state
    update_polling_method.side_effect = AttributeError

    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )

    assert hass.states.get(wemo_entity.entity_id).state == STATE_UNAVAILABLE
    pywemo_device.reconnect_with_device.assert_called_with()


async def test_async_update_with_timeout_and_recovery(hass, wemo_entity, pywemo_device):
    """Test that the entity becomes unavailable after a timeout, and that it recovers."""
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
    await async_setup_component(hass, HA_DOMAIN, {})

    with patch("async_timeout.timeout", side_effect=asyncio.TimeoutError):
        await hass.services.async_call(
            HA_DOMAIN,
            SERVICE_UPDATE_ENTITY,
            {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
            blocking=True,
        )

    assert hass.states.get(wemo_entity.entity_id).state == STATE_UNAVAILABLE

    # Check that the entity recovers and is available after the update succeeds.
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )

    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
