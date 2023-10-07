"""Entity for the nina integration."""
from dataclasses import dataclass


@dataclass
class NinaWarningData:
    """Class to hold the warning data."""

    id: str
    headline: str
    description: str
    sender: str
    severity: str
    recommended_actions: str
    affected_areas: str
    sent: str
    start: str
    expires: str
    is_valid: bool
