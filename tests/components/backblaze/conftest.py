"""Fixtures for the Backblaze integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.backblaze.const import (
    CONF_APPLICATION_KEY,
    CONF_APPLICATION_KEY_ID,
    CONF_BUCKET,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Backblaze B2",
        domain=DOMAIN,
        data={
            CONF_APPLICATION_KEY: "secret",
            CONF_APPLICATION_KEY_ID: "keyid",
            CONF_BUCKET: "bucket",
        },
        unique_id="bucket",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.backblaze.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_backblaze() -> Generator[MagicMock]:
    """Return a mocked Backblaze client."""

    bucket1 = MagicMock()
    bucket1.name = "my-bucket"
    bucket1.id_ = "bucket"
    bucket2 = MagicMock()
    bucket2.name = "my-otherbucket"
    bucket2.id_ = "bucket2"

    with (
        patch(
            "homeassistant.components.backblaze.config_flow.B2Api", autospec=True
        ) as backblaze_mock,
    ):
        backblaze = backblaze_mock.return_value
        backblaze.list_buckets.return_value = [bucket1, bucket2]

        yield backblaze
