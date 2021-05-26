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

INTRESTED_RECORD_TYPES = (DNSAddress, DNSPointer, DNSText)

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
        _LOGGER.debug("update_record: %s %s", record, now)

        if record.name not in self.types or not isinstance(
            record, INTRESTED_RECORD_TYPES
        ):
            return
        _LOGGER.debug("update_record accepted: %s %s", record, now)
        super().update_record(zc, now, record)
