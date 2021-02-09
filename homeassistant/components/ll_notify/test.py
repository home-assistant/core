"""Interactive Testing Support."""
import asyncio

from .const import DOMAIN


async def send_every_five(hass):
    """Send a test message every 5 seconds."""
    await hass.services.async_call(
        DOMAIN, "success", {"message": "TEST: from SERVER", "wait": 5}
    )

    await asyncio.sleep(5)
    await asyncio.create_task(send_every_five(hass))
