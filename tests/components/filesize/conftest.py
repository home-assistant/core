"""Fixtures for Filesize integration tests."""
from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.filesize.const import DOMAIN
from homeassistant.const import CONF_FILE_PATH

from . import TEST_FILE_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(tmp_path: Path) -> MockConfigEntry:
    """Return the default mocked config entry."""
    test_file = str(tmp_path.joinpath(TEST_FILE_NAME))
    return MockConfigEntry(
        title=TEST_FILE_NAME,
        domain=DOMAIN,
        data={CONF_FILE_PATH: test_file},
        unique_id=test_file,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.filesize.async_setup_entry", return_value=True
    ):
        yield
