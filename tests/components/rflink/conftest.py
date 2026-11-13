"""rflink conftest."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture
def mock_create_issue() -> Generator[MagicMock]:
    """Mock the create issue method."""
    with (
        patch(
            "homeassistant.components.rflink.utils.async_create_platform_config_not_supported_issue",
            autospec=True,
        ) as mock_create_issue,
    ):
        yield mock_create_issue
