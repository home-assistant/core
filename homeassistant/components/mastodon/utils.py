"""Mastodon util functions."""

from __future__ import annotations

import mimetypes
from typing import Any

from mastodon import Mastodon
from mastodon.Mastodon import Account, Instance, InstanceV2

from .const import DEFAULT_NAME


def create_mastodon_client(
    base_url: str, client_id: str, client_secret: str, access_token: str
) -> Mastodon:
    """Create a Mastodon client with the api base url."""
    return Mastodon(
        api_base_url=base_url,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
    )


def construct_mastodon_username(
    instance: InstanceV2 | Instance | None, account: Account | None
) -> str:
    """Construct a mastodon username from the account and instance."""
    if instance and account:
        if type(instance) is InstanceV2:
            return f"@{account.username}@{instance.domain}"
        return f"@{account.username}@{instance.uri}"

    return DEFAULT_NAME


def get_media_type(media_path: Any = None) -> Any:
    """Get media type."""

    (media_type, _) = mimetypes.guess_type(media_path)

    return media_type
