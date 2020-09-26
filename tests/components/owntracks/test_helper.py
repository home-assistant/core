"""Test the owntracks_http platform."""
import pytest

from homeassistant.components.owntracks import helper

from tests.async_mock import patch


@pytest.fixture(name="nacl_imported")
def mock_nacl_imported():
    """Mock a successful import."""
    with patch("homeassistant.components.owntracks.helper.nacl"):
        yield


@pytest.fixture(name="nacl_not_imported")
def mock_nacl_not_imported():
    """Mock non successful import."""
    with patch("homeassistant.components.owntracks.helper.nacl", new=None):
        yield


def test_supports_encryption(nacl_imported):
    """Test if env supports encryption."""
    assert helper.supports_encryption()


def test_supports_encryption_failed(nacl_not_imported):
    """Test if env does not support encryption."""
    assert not helper.supports_encryption()
