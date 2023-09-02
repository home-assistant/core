"""Test fixtures for mqtt component."""

from collections.abc import Generator
from random import getrandbits
from unittest.mock import patch

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def patch_hass_config(mock_hass_config: None) -> None:
    """Patch configuration.yaml."""


@pytest.fixture(autouse=True)
def mock_temp_dir() -> Generator[None, None, str]:
    """Mock the certificate temp directory."""
    with patch(
        # Patch temp dir name to avoid tests fail running in parallel
        "homeassistant.components.mqtt.util.TEMP_DIR_NAME",
        "home-assistant-mqtt" + f"-{getrandbits(10):03x}",
    ) as mocked_temp_dir:
        yield mocked_temp_dir
