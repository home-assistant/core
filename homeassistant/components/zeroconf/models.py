"""Models for Zeroconf."""

from typing import override

from zeroconf import Zeroconf
from zeroconf.asyncio import AsyncZeroconf


class HaZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""

    @override
    def close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_close = Zeroconf.close


class HaAsyncZeroconf(AsyncZeroconf):
    """Home Assistant version of AsyncZeroconf."""

    @override
    async def async_close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_async_close = AsyncZeroconf.async_close
