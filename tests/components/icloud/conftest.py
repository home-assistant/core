"""Configure iCloud tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.icloud.media_source import PhotoCache


@pytest.fixture(autouse=True)
def icloud_not_create_dir():
    """Mock component setup."""
    with patch(
        "homeassistant.components.icloud.config_flow.os.path.exists", return_value=True
    ):
        yield


@pytest.fixture(autouse=True)
def clear_photo_cache() -> None:
    """Clear the photo cache."""

    PhotoCache.instance()._cache.clear()
