"""Meteoclimatic generic test utils."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_requests():
    """Stub out services that makes requests."""
    patch_client = patch("homeassistant.components.meteoclimatic.MeteoclimaticClient")

    with patch_client:
        yield
