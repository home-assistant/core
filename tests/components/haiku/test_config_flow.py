"""Test config flow for Haiku."""
import asyncio
import concurrent.futures

from haiku import discover

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(runondifthread)
    result = future.result()

def runondifthread():
    asyncio.run(discover.discover())
if result is False:
    print("Socket Error")
