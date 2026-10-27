"""Tests for the DNS IP integration."""

import pycares


class QueryResult:
    """Return Query results."""

    def __init__(self, ip="1.2.3.4", ttl=60) -> None:
        """Initialize QueryResult class."""
        self.host = ip
        self.ttl = ttl


class RetrieveDNS:
    """Return list of test information."""

    def __init__(
        self, nameservers: list[str] | None = None, error: Exception | None = None
    ) -> None:
        """Initialize DNS class."""
        if nameservers:
            self.nameservers = nameservers
        self._nameservers = ["1.2.3.4"]
        self.error = error
        self._closed = False

    async def query_dns(
        self, host: str, qtype: str, qclass: str | None = None
    ) -> pycares.DNSResult:
        """Return dns information."""
        if self.error:
            raise self.error
        if qtype == "AAAA":
            results = pycares.DNSResult(
                answer=[
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_AAAA,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.AAAARecordData(addr="2001:db8:77::face:b00c"),
                        ttl=60,
                    ),
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_AAAA,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.AAAARecordData(addr="2001:db8:77::dead:beef"),
                        ttl=60,
                    ),
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_AAAA,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.AAAARecordData(addr="2001:db8::77:dead:beef"),
                        ttl=60,
                    ),
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_AAAA,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.AAAARecordData(addr="2001:db8:66::dead:beef"),
                        ttl=60,
                    ),
                ],
                authority=[],
                additional=[],
            )
        else:
            results = pycares.DNSResult(
                answer=[
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_CNAME,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.CNAMERecordData(cname="test.testing.com"),
                        ttl=60,
                    ),
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_A,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.ARecordData(addr="1.2.3.4"),
                        ttl=60,
                    ),
                    pycares.DNSRecord(
                        name="test",
                        type=pycares.QUERY_TYPE_A,
                        record_class=pycares.QUERY_CLASS_IN,
                        data=pycares.ARecordData(addr="1.1.1.1"),
                        ttl=60,
                    ),
                ],
                authority=[],
                additional=[],
            )
        return results

    @property
    def nameservers(self) -> list[str]:
        """Return nameserver."""
        return self._nameservers

    @nameservers.setter
    def nameservers(self, value: list[str]) -> None:
        self._nameservers = value

    async def close(self) -> None:
        """Close the resolver."""
        self._closed = True
