"""Common code tests."""
from datetime import timedelta
from unittest.mock import MagicMock

from pyHS100 import SmartDeviceException

from homeassistant.components.tplink.common import async_add_entities_retry
from homeassistant.helpers.typing import HomeAssistantType


async def test_async_add_entities_retry(
        hass: HomeAssistantType
):
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

    objects = [
        "Object 1",
        "Object 2",
        "Object 3",
        "Object 4",
    ]
    await async_add_entities_retry(
        hass,
        async_add_entities_callback,
        objects,
        callback,
        interval=timedelta(milliseconds=100)
    )
    await hass.async_block_till_done()

    assert callback.call_count == len(callback_side_effects)


async def test_async_add_entities_retry_cancel(
        hass: HomeAssistantType
):
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

    objects = [
        "Object 1",
        "Object 2",
        "Object 3",
        "Object 4",
    ]
    cancel = await async_add_entities_retry(
        hass,
        async_add_entities_callback,
        objects,
        callback,
        interval=timedelta(milliseconds=100)
    )
    cancel()
    await hass.async_block_till_done()

    assert callback.call_count == 4
