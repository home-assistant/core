"""Test config flow for Haiku."""
import asyncio

from haiku import discover

result = asyncio.run(discover.discover())
if result is False:
    print("Socket Error")
