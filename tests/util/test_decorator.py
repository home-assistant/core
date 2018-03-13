"""Test decorator utils."""
import asyncio
import random

from homeassistant.util import decorator


async def test_async_join_concurrent(loop):
    """Test the async_join_concurrent decorator."""
    results = []

    @decorator.async_join_concurrent
    async def work():
        """Do some work."""
        return random.random()

    async def append():
        """Append value to results after doing work."""
        results.append(await work())

    asyncio.ensure_future(append())
    asyncio.ensure_future(append())
    asyncio.ensure_future(append())
    asyncio.ensure_future(append())

    # Finish all our futures
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(set(results)) == 1

    asyncio.ensure_future(append())
    asyncio.ensure_future(append())
    asyncio.ensure_future(append())
    asyncio.ensure_future(append())

    # Finish all our futures
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert len(set(results)) == 2
