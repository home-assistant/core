"""Tests for the dnsip integration."""

from __future__ import annotations


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

    async def query(self, hostname, qtype) -> list[QueryResult]:
        """Return information."""
        if self.error:
            raise self.error
        if qtype == "AAAA":
            results = [
                QueryResult("2001:db8:77::face:b00c"),
                QueryResult("2001:db8:77::dead:beef"),
                QueryResult("2001:db8::77:dead:beef"),
                QueryResult("2001:db8:66::dead:beef"),
            ]
        else:
            results = [QueryResult("1.2.3.4"), QueryResult("1.1.1.1")]
        return results

    @property
    def nameservers(self) -> list[str]:
        """Return nameserver."""
        return self._nameservers

    @nameservers.setter
    def nameservers(self, value: list[str]) -> None:
        self._nameservers = value
