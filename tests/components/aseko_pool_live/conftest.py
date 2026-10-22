"""Aseko Pool Live conftest."""

from aioaseko import User
import pytest

from homeassistant.util import dt as dt_util


@pytest.fixture
def user() -> User:
    """Aseko User fixture."""
    return User(
        user_id="a_user_id",
        created_at=dt_util.utcnow(),
        updated_at=dt_util.utcnow(),
        name="John",
        surname="Doe",
        language="any_language",
        is_active=True,
    )
