"""Models for Zeroconf."""

import asyncio
from typing import Any

from zeroconf import DNSAddress, DNSRecord, ServiceBrowser, Zeroconf
from zeroconf.asyncio import AsyncZeroconf

TYPE_AAAA = 28


class HaZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""

    def close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_close = Zeroconf.close


class HaAsyncZeroconf(AsyncZeroconf):
    """Home Assistant version of AsyncZeroconf."""

    def __init__(  # pylint: disable=super-init-not-called
        self, *args: Any, **kwargs: Any
    ) -> None:
        """Wrap AsyncZeroconf."""
        self.zeroconf = HaZeroconf(*args, **kwargs)
        self.loop = asyncio.get_running_loop()

    async def async_close(self) -> None:
        """Fake method to avoid integrations closing it."""


class HaServiceBrowser(ServiceBrowser):
    """ServiceBrowser that only consumes DNSPointer records."""

    def __init__(self, ipv6: bool, *args: Any, **kwargs: Any) -> None:
        """Create service browser that filters ipv6 if it is disabled."""
        self.ipv6 = ipv6
        super().__init__(*args, **kwargs)
        self.name = "HaServiceBrowser"

    def update_record(self, zc: Zeroconf, now: float, record: DNSRecord) -> None:
        """Pre-Filter AAAA records if IPv6 is not enabled."""
        if (
            not self.ipv6
            and isinstance(record, DNSAddress)
            and record.type == TYPE_AAAA
        ):
            return
        super().update_record(zc, now, record)
