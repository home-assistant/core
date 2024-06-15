"""TOD."""

import aiohttp


class ScRpiClient:
    """Provides operations to invoke on a Strip Controller device."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the client."""
        self.session = session

    async def connect(self):
        """TOD:CONTINUE PASS THE CORRECT URL."""
        async with self.session.ws_connect("http://localhost:8080") as ws:
            await ws.send_str("/answer")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "close cmd":
                        await ws.close()
                        break
                    await ws.send_str(msg.data + "/answer")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
