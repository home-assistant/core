"""Common code tests."""
from datetime import timedelta

from pyHS100 import SmartDeviceException

from homeassistant.components.tplink.common import async_add_entities_retry
from homeassistant.helpers.typing import HomeAssistantType

from tests.async_mock import MagicMock


async def test_async_add_entities_retry(hass: HomeAssistantType):
    """Test interval callback."""
    async_add_entities_callback = MagicMock()

    # The objects that will be passed to async_add_entities_callback.
    objects = ["Object 1", "Object 2", "Object 3", "Object 4"]

    # For each call to async_add_entities_callback, the following side effects
    # will be triggered in order. This set of side effects accurateley simulates
    # 3 attempts to add all entities while also handling several return types.
    # To help understand what's going on, a comment exists describing what the
    # object list looks like throughout the iterations.
    callback_side_effects = [
        # OB1, OB2, OB3, OB4
        False,
        False,
        True,  # Object 3
        False,
        # OB1, OB2, OB4
        True,  # Object 1
        SmartDeviceException("My error"),
        False,
        # OB2, OB4
        True,  # Object 2
        True,  # Object 4
    ]

    callback = MagicMock(side_effect=callback_side_effects)

    await async_add_entities_retry(
        hass,
        async_add_entities_callback,
        objects,
        callback,
        interval=timedelta(milliseconds=100),
    )
    await hass.async_block_till_done()

    assert callback.call_count == len(callback_side_effects)


async def test_async_add_entities_retry_cancel(hass: HomeAssistantType):
    """Test interval callback."""
    async_add_entities_callback = MagicMock()

    callback_side_effects = [
        False,
        False,
        True,  # Object 1
        False,
        True,  # Object 2
        SmartDeviceException("My error"),
        False,
        True,  # Object 3
        True,  # Object 4
    ]

    callback = MagicMock(side_effect=callback_side_effects)

    objects = ["Object 1", "Object 2", "Object 3", "Object 4"]
    cancel = await async_add_entities_retry(
        hass,
        async_add_entities_callback,
        objects,
        callback,
        interval=timedelta(milliseconds=100),
    )
    cancel()
    await hass.async_block_till_done()

    assert callback.call_count == 4
