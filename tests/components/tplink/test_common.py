"""Common code tests."""
from datetime import timedelta
from unittest.mock import MagicMock, patch

from pyHS100 import SmartDeviceException

from homeassistant.components.tplink.common import async_add_entities_retry


@patch('homeassistant.components.tplink.common.async_track_time_interval')
def test_async_add_entities_retry(hass):
    """Test interval callback."""
    def interval_func(hass, process_func, interval):
        process_func()
        process_func()
        process_func()

    interval_patch = patch(
        'homeassistant.components.tplink.common.async_track_time_interval',
        side_effect=interval_func
    )
    with interval_patch:
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
        async_add_entities_retry(
            hass,
            async_add_entities_callback,
            objects,
            callback,
            interval=timedelta(milliseconds=100)
        )
        hass.block_till_done()

        assert callback.call_count == len(callback_side_effects)
