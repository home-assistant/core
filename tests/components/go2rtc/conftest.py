"""Go2rtc test configuration."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from tests.components.smhi.common import AsyncMock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.go2rtc.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock a go2rtc client."""
    with (
        patch(
            "homeassistant.components.go2rtc.Go2RtcClient",
        ) as mock_client,
        patch(
            "homeassistant.components.go2rtc.config_flow.Go2RtcClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.streams.list = AsyncMock(return_value=[])
        yield client
