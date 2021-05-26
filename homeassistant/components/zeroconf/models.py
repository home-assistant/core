"""Models for Zeroconf."""

import asyncio
import logging
from typing import Any

from zeroconf import (
    DNSAddress,
    DNSPointer,
    DNSRecord,
    DNSText,
    ServiceBrowser,
    Zeroconf,
)
from zeroconf.asyncio import AsyncZeroconf


_LOGGER = logging.getLogger(__name__)


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

    def update_record(self, zc: Zeroconf, now: float, record: DNSRecord) -> None:
        """Pre-Filter update_record to INTRESTED_RECORD_TYPES for the configured type."""
        #
        # To avoid overwhemling the system we pre-filter here and only process
        # INTRESTED_RECORD_TYPES for the configured record name (type)
        #
        if isinstance(record, DNSPointer) and record.name not in self.types:
            return
        
        _LOGGER.debug("update_record: (name=%s) %s %s", record.name, record, now)
        if isinstance(record, DNSAddress):
            _LOGGER.debug("Entries with server (%s): %s", record.name, self.zc.cache.entries_with_server(record.name))
            #return
        #if isinstance(
        #    record, INTRESTED_RECORD_TYPES
        #):
        #    return
        #_LOGGER.debug("update_record accepted: %s %s", record, now)
        super().update_record(zc, now, record)
        #SERVICE_RECORD_TYPES = (DNSAddress, DNSText)
