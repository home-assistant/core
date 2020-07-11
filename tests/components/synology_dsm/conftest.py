"""Configure Synology DSM tests."""
import pytest

from tests.async_mock import patch


@pytest.fixture(name="bypass_setup", autouse=True)
def bypass_setup_fixture():
    """Mock component setup."""
    with patch(
        "homeassistant.components.synology_dsm.async_setup_entry", return_value=True
    ):
        yield
