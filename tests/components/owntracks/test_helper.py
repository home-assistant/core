"""Test the owntracks_http platform."""
from unittest.mock import patch
import pytest

from homeassistant.components.owntracks.helper import supports_encryption


@pytest.fixture(name="nacl_imported")
def mock_nacl_imported():
    """Mock a successful closing session."""
    with patch("nacl"):
        yield


@pytest.fixture(name="nacl_not_imported")
def mock_nacl_not_imported():
    """Mock a successful closing session."""
    with patch("nacl", side_effect=ImportError()):
        yield


def test_supports_encryption(nacl_imported):
    """Test if env supports encryption."""
    assert supports_encryption()


def test_supports_encryption_failed(nacl_not_imported):
    """Test if env does not support encryption."""
    assert not supports_encryption()
