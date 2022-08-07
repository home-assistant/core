"""Define test fixtures for Prosegur."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="mock_prosegur_auth")
def mock_prosegur_auth():
    """Setups authentication."""

    with patch("pyprosegur.auth.Auth.login", return_value=True):
        yield
