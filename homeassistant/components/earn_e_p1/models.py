"""Models for the EARN-E P1 Meter integration."""

import asyncio
from dataclasses import dataclass, field

from earn_e_p1 import EarnEP1Listener


@dataclass
class EarnEP1Data:
    """Shared UDP listener and the config entries currently using it."""

    # Entries set up concurrently at startup, so creating and stopping the
    # listener must not interleave or two of them race to bind the UDP port.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    listener: EarnEP1Listener | None = None
    entries: set[str] = field(default_factory=set)
