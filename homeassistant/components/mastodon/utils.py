"""Mastodon util functions."""

from __future__ import annotations

from mastodon import Mastodon

from .const import ACCOUNT_USERNAME, DEFAULT_NAME, INSTANCE_DOMAIN, INSTANCE_URI


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
    instance: dict[str, str] | None, account: dict[str, str] | None
) -> str:
    """Construct a mastodon username from the account and instance."""
    if instance and account:
        return (
            f"@{account[ACCOUNT_USERNAME]}@"
            f"{instance.get(INSTANCE_URI, instance.get(INSTANCE_DOMAIN))}"
        )

    return DEFAULT_NAME
