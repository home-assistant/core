"""Fixtures for Filesize integration tests."""
from __future__ import annotations

from collections.abc import Generator
import os
from unittest.mock import patch

import pytest

from homeassistant.components.filesize.const import DOMAIN
from homeassistant.const import CONF_FILE_PATH

from . import TEST_FILE, TEST_FILE2, TEST_FILE_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_FILE_NAME,
        domain=DOMAIN,
        data={CONF_FILE_PATH: TEST_FILE},
        unique_id=TEST_FILE,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.filesize.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture(autouse=True)
def remove_file() -> None:
    """Remove test file."""
    yield
    if os.path.isfile(TEST_FILE):
        os.remove(TEST_FILE)
    if os.path.isfile(TEST_FILE2):
        os.remove(TEST_FILE2)
