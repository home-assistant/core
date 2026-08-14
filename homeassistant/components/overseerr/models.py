"""Data models for Overseerr integration."""

from dataclasses import dataclass

from python_overseerr import IssueCount, RequestCount


@dataclass
class OverseerrData:
    """Data model for Overseerr coordinator."""

    requests: RequestCount
    issues: IssueCount
