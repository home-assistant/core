"""Common fixtures for the Flow-it tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


def get_mock_vmc(
    info_hostname: str = "Flow-it Device",
    state_name: str = "00:11:22:33:44:55",
    exception: Exception | None = None,
) -> AsyncMock:
    """Return a mock FlowItVMCMachine context manager."""
    mock_vmc = AsyncMock()
    mock_vmc.get_info.return_value.hostname = info_hostname
    mock_vmc.state.name = state_name

    if exception:
        mock_vmc.get_info.side_effect = exception

    return mock_vmc


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.flow_it.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
