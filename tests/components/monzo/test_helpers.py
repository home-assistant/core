"""Tests for Monzo helpers."""

from homeassistant.components.monzo.helpers import (
    get_account_name,
    get_authenticated_owner_name,
)


def test_authenticated_owner_name_without_user_id() -> None:
    """Test an owner cannot be selected without an authenticated user ID."""
    assert get_authenticated_owner_name([], None) is None


def test_account_name_ignores_malformed_owner() -> None:
    """Test malformed owner metadata does not affect a joint account name."""
    account = {
        "name": "Joint Account",
        "owners": [
            "invalid owner",
            {"preferred_name": "Jake Martin"},
            {"preferred_name": "Jane Martin"},
        ],
    }

    assert get_account_name(account) == "Joint Account — Jake Martin & Jane Martin"
