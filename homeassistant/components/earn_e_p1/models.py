"""Models for the EARN-E P1 Meter integration."""

from dataclasses import dataclass, field

from earn_e_p1 import EarnEP1Listener


@dataclass
class EarnEP1Data:
    """Shared UDP listener and the config entries currently using it."""

    listener: EarnEP1Listener
    entries: set[str] = field(default_factory=set)
