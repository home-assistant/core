"""Aseko Pool Live conftest."""

from datetime import datetime

from aioaseko import User
import pytest


@pytest.fixture
def user() -> User:
    """Aseko User fixture."""
    return User(
        user_id="a_user_id",
        created_at=datetime.now(),
        updated_at=datetime.now(),
        name="John",
        surname="Doe",
        language="any_language",
        is_active=True,
    )
