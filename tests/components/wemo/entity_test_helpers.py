"""Test cases that are in common among wemo platform modules.

This is not a test module. These test methods are used by the platform test modules.
"""

import asyncio
from collections.abc import Callable, Coroutine
import threading
from typing import Any

import pywemo

from homeassistant.components.homeassistant import DOMAIN as HA_DOMAIN
from homeassistant.components.wemo.coordinator import async_get_coordinator
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


def _perform_registry_callback(coordinator):
    """Return a callable method to trigger a state callback from the device."""

    async def async_callback():
        await coordinator.hass.async_add_executor_job(
            coordinator.subscription_callback, coordinator.wemo, "", ""
        )

    return async_callback


def _perform_async_update(coordinator):
    """Return a callable method to cause hass to update the state of the entity."""

    async def async_callback():
        await coordinator._async_update_data()

    return async_callback


async def _async_multiple_call_helper(
    hass: HomeAssistant,
    pywemo_device: pywemo.WeMoDevice,
    call1: Callable[[], Coroutine[Any, Any, None]],
    call2: Callable[[], Coroutine[Any, Any, None]],
) -> None:
    """Create two calls (call1 & call2) in parallel; verify only one polls the device.

    There should only be one poll on the device at a time. Any parallel updates
    # that happen at the same time should be ignored. This is verified by blocking
    in the get_state method. The polling method should only be called once as a
    result of calling call1 & call2 simultaneously.
    """
    event = threading.Event()
    waiting = asyncio.Event()
    call_count = 0

    def get_state(force_update=None):
        if force_update is None:
            return
        nonlocal call_count
        call_count += 1
        hass.loop.call_soon_threadsafe(waiting.set)
        event.wait()

    # Danger! Do not use a Mock side_effect here. The test will deadlock. When
    # called though hass.async_add_executor_job, Mock objects !surprisingly!
    # run in the same thread as the asyncio event loop.
    # https://github.com/home-assistant/core/blob/1ba5c1c9fb1e380549cb655986b5f4d3873d7352/tests/common.py#L179
    pywemo_device.get_state = get_state

    # One of these two calls will block on `event`. The other will return right
    # away because the `_update_lock` is held.
    done, pending = await asyncio.wait(
        [asyncio.create_task(call1()), asyncio.create_task(call2())],
        return_when=asyncio.FIRST_COMPLETED,
    )
    _ = [d.result() for d in done]  # Allow any exceptions to be raised.

    # Allow the blocked call to return.
    await waiting.wait()
    event.set()

    if pending:
        done, _ = await asyncio.wait(pending)
        _ = [d.result() for d in done]  # Allow any exceptions to be raised.

    # Make sure the state update only happened once.
    assert call_count == 1


async def test_async_update_locked_callback_and_update(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice, wemo_entity: er.RegistryEntry
) -> None:
    """Test that a callback and a state update request can't both happen at the same time.

    When a state update is received via a callback from the device at the same time
    as hass is calling `async_update`, verify that only one of the updates proceeds.
    """
    coordinator = async_get_coordinator(hass, wemo_entity.device_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    callback = _perform_registry_callback(coordinator)
    update = _perform_async_update(coordinator)
    await _async_multiple_call_helper(hass, pywemo_device, callback, update)


async def test_async_update_locked_multiple_updates(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice, wemo_entity: er.RegistryEntry
) -> None:
    """Test that two hass async_update state updates do not proceed at the same time."""
    coordinator = async_get_coordinator(hass, wemo_entity.device_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    update = _perform_async_update(coordinator)
    await _async_multiple_call_helper(hass, pywemo_device, update, update)


async def test_async_update_locked_multiple_callbacks(
    hass: HomeAssistant, pywemo_device: pywemo.WeMoDevice, wemo_entity: er.RegistryEntry
) -> None:
    """Test that two device callback state updates do not proceed at the same time."""
    coordinator = async_get_coordinator(hass, wemo_entity.device_id)
    await async_setup_component(hass, HA_DOMAIN, {})
    callback = _perform_registry_callback(coordinator)
    await _async_multiple_call_helper(hass, pywemo_device, callback, callback)


async def test_avaliable_after_update(
    hass: HomeAssistant, pywemo_registry, pywemo_device, wemo_entity, domain
) -> None:
    """Test the availability when an On call fails and after an update.

    This test expects that the pywemo_device Mock has been setup to raise an
    ActionException when the SERVICE_TURN_ON method is called and that the
    state will be On after the update.
    """
    await hass.services.async_call(
        domain,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_UNAVAILABLE

    pywemo_registry.callbacks[pywemo_device.name](pywemo_device, "", "")
    await hass.async_block_till_done()
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON


async def test_turn_off_state(hass: HomeAssistant, wemo_entity, domain) -> None:
    """Test that the device state is updated after turning off."""
    await hass.services.async_call(
        domain,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF


class EntityTestHelpers:
    """Common state update helpers."""

    async def test_async_update_locked_multiple_updates(
        self,
        hass: HomeAssistant,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Test that two hass async_update state updates do not proceed at the same time."""
        await test_async_update_locked_multiple_updates(
            hass, pywemo_device, wemo_entity
        )

    async def test_async_update_locked_multiple_callbacks(
        self,
        hass: HomeAssistant,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Test that two device callback state updates do not proceed at the same time."""
        await test_async_update_locked_multiple_callbacks(
            hass, pywemo_device, wemo_entity
        )

    async def test_async_update_locked_callback_and_update(
        self,
        hass: HomeAssistant,
        pywemo_device: pywemo.WeMoDevice,
        wemo_entity: er.RegistryEntry,
    ) -> None:
        """Test that a callback and a state update request can't both happen at the same time.

        When a state update is received via a callback from the device at the same time
        as hass is calling `async_update`, verify that only one of the updates proceeds.
        """
        await test_async_update_locked_callback_and_update(
            hass, pywemo_device, wemo_entity
        )
