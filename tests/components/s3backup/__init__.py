"""Fixtures for the S3 integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.s3backup.const import (
    CONF_ACCESS_KEY,
    CONF_BUCKET,
    CONF_S3_URL,
    CONF_SECRET_KEY,
    DOMAIN,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="S3 Backup",
        domain=DOMAIN,
        data={
            CONF_ACCESS_KEY: "secret",
            CONF_SECRET_KEY: "keyid",
            CONF_BUCKET: "bucket",
            CONF_S3_URL: "http://example.com",
        },
        unique_id="bucket",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.s3backup.async_setup_entry", return_value=True
    ):
        yield


@pytest.fixture
def mock_s3backup() -> Generator[MagicMock]:
    """Return a mocked S3 client."""

    bucket1 = MagicMock()
    bucket1.name = "my-bucket"
    bucket2 = MagicMock()
    bucket2.name = "my-otherbucket"

    with (
        patch(
            "homeassistant.components.s3backup.config_flow.get_buckets", autospec=True
        ) as s3backup_mock,
    ):
        s3backup_mock.return_value = [bucket1, bucket2]

        yield s3backup_mock
