"""Configure Synology DSM tests."""
import pytest

from tests.async_mock import patch


def pytest_configure(config):
    """Register custom marker for tests."""
    config.addinivalue_line(
        "markers", "no_bypass_setup: mark test to disable bypass_setup_fixture"
    )


@pytest.fixture(name="bypass_setup", autouse=True)
def bypass_setup_fixture(request):
    """Mock component setup."""
    if "no_bypass_setup" in request.keywords:
        yield
    else:
        with patch(
            "homeassistant.components.synology_dsm.async_setup_entry", return_value=True
        ):
            yield
