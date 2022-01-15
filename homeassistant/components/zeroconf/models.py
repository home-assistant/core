"""Models for Zeroconf."""

from typing import Any

from zeroconf import DNSAddress, DNSRecord, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

TYPE_AAAA = 28


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


class HaAsyncServiceBrowser(AsyncServiceBrowser):
    """ServiceBrowser that only consumes DNSPointer records."""

    def __init__(self, ipv6: bool, *args: Any, **kwargs: Any) -> None:
        """Create service browser that filters ipv6 if it is disabled."""
        self.ipv6 = ipv6
        super().__init__(*args, **kwargs)

    def update_record(self, zc: Zeroconf, now: float, record: DNSRecord) -> None:
        """Pre-Filter AAAA records if IPv6 is not enabled."""
        if (
            not self.ipv6
            and isinstance(record, DNSAddress)
            and record.type == TYPE_AAAA
        ):
            return
        super().update_record(zc, now, record)
