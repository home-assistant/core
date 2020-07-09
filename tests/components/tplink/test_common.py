"""Common code tests."""
import asyncio
from datetime import timedelta

from asynctest import CoroutineMock
from kasa import SmartDeviceException

from homeassistant.components.tplink.common import async_add_entities_retry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


async def test_async_add_entities_retry(hass: HomeAssistantType):
    """Test interval callback."""
    async_add_entities_callback = CoroutineMock()

    # The objects that will be passed to async_add_entities_callback.
    objects = ["Object 1", "Object 2", "Object 3", "Object 4"]

    # For each call to async_add_entities_callback, the following side effects
    # will be triggered in order. This set of side effects accuratley simulates
    # 3 attempts to add all entities while also handling several return types.
    # To help understand what's going on, a comment exists describing what the
    # object list looks like throughout the iterations.
    callback_side_effects = [
        # Interval pass 1
        False,  # Object 1
        False,  # Object 2
        True,  # Object 3
        False,  # Object 4
        # Interval pass 2
        True,  # Object 1
        SmartDeviceException("My error"),  # Object 2
        False,  # Object 4
        # Interval pass 3
        True,  # Object 2
        True,  # Object 4
    ]

    callback = CoroutineMock(side_effect=callback_side_effects)
    start_time = dt_util.utcnow()

    await async_add_entities_retry(hass, async_add_entities_callback, objects, callback)
    async_fire_time_changed(hass, start_time + timedelta(seconds=10))
    await asyncio.sleep(0.1)
    assert callback.call_count == 4

    callback.reset_mock()
    async_fire_time_changed(hass, start_time + timedelta(seconds=61))
    await asyncio.sleep(0.1)
    assert callback.call_count == 3

    callback.reset_mock()
    async_fire_time_changed(hass, start_time + timedelta(seconds=61))
    await asyncio.sleep(0.1)
    assert callback.call_count == 2


async def test_async_add_entities_retry_cancel(hass: HomeAssistantType):
    """Test interval callback."""
    async_add_entities_callback = CoroutineMock()

    # The objects that will be passed to async_add_entities_callback.
    objects = ["Object 1", "Object 2", "Object 3", "Object 4"]

    callback_side_effects = [
        # Interval pass 1
        False,  # Object 1
        False,  # Object 2
        True,  # Object 3
        False,  # Object 4
        # Interval pass 2
        True,  # Object 1
        SmartDeviceException("My error"),  # Object 2
        False,  # Object 4
        # Interval pass 3
        True,  # Object 2
        True,  # Object 4
    ]

    callback = CoroutineMock(side_effect=callback_side_effects)
    start_time = dt_util.utcnow()

    cancel = await async_add_entities_retry(
        hass, async_add_entities_callback, objects, callback
    )
    async_fire_time_changed(hass, start_time + timedelta(seconds=10))
    await asyncio.sleep(0.1)
    assert callback.call_count == 4

    callback.reset_mock()
    async_fire_time_changed(hass, start_time + timedelta(seconds=61))
    await asyncio.sleep(0.1)
    assert callback.call_count == 3

    cancel()

    callback.reset_mock()
    async_fire_time_changed(hass, start_time + timedelta(seconds=61))
    await asyncio.sleep(0.1)
    assert callback.call_count == 0
