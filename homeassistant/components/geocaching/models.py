"""Models for the Geocaching integration."""
from typing import TypedDict


class GeocachingOAuthApiUrls(TypedDict):
    """oAuth2 urls for a single environment."""

    authorize_url: str
    token_url: str
