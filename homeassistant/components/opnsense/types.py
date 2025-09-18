"""Types for OPNsense integration."""

from typing import NewType, TypedDict


class APIData(TypedDict):
    """API data for OPNsense."""

    api_key: str
    api_secret: str
    base_url: str
    verify_cert: bool


Interfaces = NewType("Interfaces", list[str])
