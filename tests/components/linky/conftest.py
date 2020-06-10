"""Linky generic test utils."""
import pytest

from tests.async_mock import patch


@pytest.fixture(autouse=True)
def patch_fakeuseragent():
    """Stub out fake useragent dep that makes requests."""
    with patch("pylinky.client.UserAgent", return_value="Test Browser"):
        yield
