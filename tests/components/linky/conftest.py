"""Linky generic test utils."""
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def patch_fakeuseragent():
    """Stub out fake useragent dep that makes requests."""
    with patch("pylinky.client.UserAgent", return_value="Test Browser"):
        yield
