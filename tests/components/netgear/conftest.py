"""Configure Netgear tests."""
import pytest

from tests.async_mock import patch


@pytest.fixture(name="bypass_setup", autouse=True)
def bypass_setup_fixture():
    """Mock component setup."""
    with patch("homeassistant.components.netgear.async_setup_entry", return_value=True):
        yield
