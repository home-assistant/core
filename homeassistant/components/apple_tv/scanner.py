"""Scanner for apple_tv that uses HomeAssistant zeroconf."""
from __future__ import annotations

from pyatv import interface
from pyatv.const import Protocol
from pyatv.protocols import PROTOCOLS


async def scan(
    timeout: int = 5,
    identifier: str | set[str] | None = None,
    protocol: Protocol | set[Protocol] | None = None,
    hosts: list[str] = None,
) -> list[interface.BaseConfig]:
    """Scan using running zeroconf instead of pyatvs built-in scanner."""
    import pprint

    pprint.pprint([timeout, identifier, protocol, hosts])
