"""Utils for bluesound tests."""

import asyncio
from typing import Any


def mock_long_poll(value: Any):
    """Use for mocking long-polling calls(status, sync_status).

    The first call will return immediately.All subsequent calls will return after a 1 second delay. This avoids a busy loop in tests.
    """
    first_call = True
    async def delay(*args, **kwargs):
        nonlocal first_call
        if not first_call:
            await asyncio.sleep(1)
        first_call = False
        return value

    return delay
