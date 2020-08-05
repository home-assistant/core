"""Test config flow for Haiku."""
import asyncio

from haiku import discover

if asyncio.run(discover.discover()) == False:
    print("[HAIKU] Error: Socket Error")
    
