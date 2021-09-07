"""Shared useful methods for Poolstation integration."""

from pypoolstation import Account


def create_account(session, email, password, logger=None):
    """Create a pypoolstation.Account object with the given email, password."""
    return Account(session, username=email, password=password, logger=logger)
