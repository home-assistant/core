"""Provide common smhi fixtures."""
import pytest

from tests.common import load_fixture


@pytest.fixture(scope="session")
def api_response():
    """Return an API response."""
    return load_fixture("smhi.json")
