"""Common fixtures for Rova tests."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_rova():
    """Mock a successful Rova API."""
    api = MagicMock()

    with (
        patch(
            "homeassistant.components.rova.config_flow.Rova",
            return_value=api,
        ) as api,
        patch("homeassistant.components.rova.Rova", return_value=api),
    ):
        api.is_rova_area.return_value = True
        yield api
