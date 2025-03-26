"""Tests for the Bosch Alarm component."""
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant


async def call_observable(hass: HomeAssistant, observable: AsyncMock) -> None:
    """Call the observable with the given event."""
    for callback in observable.attach.call_args_list:
        callback[0][0]()
    await hass.async_block_till_done()