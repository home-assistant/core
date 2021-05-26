"""Models for Zeroconf."""

import asyncio
import logging
from typing import Any

from zeroconf import DNSAddress, DNSPointer, DNSRecord, ServiceBrowser, Zeroconf
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

    def _record_has_browser_type(self, record: DNSRecord) -> bool:
        """Check if the record is one of the types we are browsing."""
        return any(record.name.endswith(type_) for type_ in self.types)

    def update_record(self, zc: Zeroconf, now: float, record: DNSRecord) -> None:
        """Pre-Filter update_record to INTRESTED_RECORD_TYPES for the configured type."""
        #
        # To avoid overwhemling the system we pre-filter here
        #
        if isinstance(record, DNSPointer):
            if record.name not in self.types:
                _LOGGER.debug(
                    "REJECT update_record: (name=%s) %s %s", record.name, record, now
                )
                return
        elif isinstance(record, DNSAddress):
            _LOGGER.debug(
                "EXISTING updates_record: (name=%s) %s: cache -> %s",
                record.name,
                record,
                zc.cache.entries_with_name(record.name),
            )
            if not any(
                self._record_has_browser_type(service)
                for service in self.zc.cache.entries_with_server(record.name)
            ):
                _LOGGER.debug(
                    "REJECT update_record: (name=%s) %s %s", record.name, record, now
                )
        #                return
        elif not self._record_has_browser_type(record):
            _LOGGER.debug(
                "REJECT update_record: (name=%s) %s %s", record.name, record, now
            )
            return
        _LOGGER.debug("ACCEPT update_record: (name=%s) %s %s", record.name, record, now)

        # return
        # if isinstance(
        #    record, INTRESTED_RECORD_TYPES
        # ):
        #    return
        # _LOGGER.debug("update_record accepted: %s %s", record, now)
        super().update_record(zc, now, record)
        # SERVICE_RECORD_TYPES = (DNSAddress, DNSText)
