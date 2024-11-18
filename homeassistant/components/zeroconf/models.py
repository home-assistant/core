"""Models for Zeroconf."""

from zeroconf import Zeroconf
from zeroconf.asyncio import AsyncZeroconf


class HaZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""

    def close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_close = Zeroconf.close


class HaAsyncZeroconf(AsyncZeroconf):
    """Home Assistant version of AsyncZeroconf."""

    async def async_close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_async_close = AsyncZeroconf.async_close
