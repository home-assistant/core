"""Models for Zeroconf."""

from zeroconf import DNSPointer, DNSRecord, ServiceBrowser, Zeroconf


class HaZeroconf(Zeroconf):
    """Zeroconf that cannot be closed."""

    def close(self) -> None:
        """Fake method to avoid integrations closing it."""

    ha_close = Zeroconf.close


class HaServiceBrowser(ServiceBrowser):
    """ServiceBrowser that only consumes DNSPointer records."""

    def update_record(self, zc: Zeroconf, now: float, record: DNSRecord) -> None:
        """Pre-Filter update_record to DNSPointers for the configured type."""

        #
        # Each ServerBrowser currently runs in its own thread which
        # processes every A or AAAA record update per instance.
        #
        # As the list of zeroconf names we watch for grows, each additional
        # ServiceBrowser would process all the A and AAAA updates on the network.
        #
        # To avoid overwhemling the system we pre-filter here and only process
        # DNSPointers for the configured record name (type)
        #
        if record.name not in self.types or not isinstance(record, DNSPointer):
            return
        super().update_record(zc, now, record)
