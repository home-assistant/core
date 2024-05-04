"""Provide common smhi fixtures."""

import pytest

from homeassistant.components.smhi.const import DOMAIN

from tests.common import load_fixture


@pytest.fixture(scope="package")
def api_response():
    """Return an API response."""
    return load_fixture("smhi.json", DOMAIN)


@pytest.fixture(scope="package")
def api_response_lack_data():
    """Return an API response."""
    return load_fixture("smhi_short.json", DOMAIN)
