"""Helpers for the Monzo integration."""

from collections.abc import Iterable
from typing import Any


def get_authenticated_owner_name(
    accounts: Iterable[dict[str, Any]], user_id: str | None
) -> str | None:
    """Return the preferred name for the authenticated Monzo owner."""
    if user_id is None:
        return None

    for account in accounts:
        if not isinstance(owners := account.get("owners"), list):
            continue
        for owner in owners:
            if not isinstance(owner, dict) or owner.get("user_id") != user_id:
                continue
            for key in ("preferred_name", "preferred_first_name"):
                if isinstance(name := owner.get(key), str) and name:
                    return name
    return None


def get_account_name(account: dict[str, Any]) -> str:
    """Return a descriptive name for a Monzo account."""
    owner_names: list[str] = []
    if isinstance(owners := account.get("owners"), list):
        for owner in owners:
            if not isinstance(owner, dict):
                continue
            for key in ("preferred_name", "preferred_first_name"):
                if isinstance(name := owner.get(key), str) and name:
                    owner_names.append(name)
                    break

    account_name: str = account["name"]
    if len(owner_names) < 2:
        return account_name
    return f"{account_name} — {' & '.join(owner_names)}"
