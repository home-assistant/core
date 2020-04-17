"""Configure Synology DSM tests."""
from unittest.mock import patch

import pytest


@pytest.fixture(name="dsm_bypass_setup", autouse=True)
def dsm_bypass_setup_fixture():
    """Mock component setup."""
    with patch(
        "homeassistant.components.synology_dsm.async_setup_entry", return_value=True
    ):
        yield
