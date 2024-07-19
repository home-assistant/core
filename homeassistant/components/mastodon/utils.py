"""Mastodon util functions."""

from __future__ import annotations

from mastodon import Mastodon


def create_mastodon_instance(
    base_url: str, client_id: str, client_secret: str, access_token: str
) -> Mastodon:
    """Create a Mastodon instance with the api base url."""
    return Mastodon(
        api_base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
    )
