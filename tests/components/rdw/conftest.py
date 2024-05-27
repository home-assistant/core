"""Fixtures for RDW integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from vehicle import Vehicle

from homeassistant.components.rdw.const import CONF_LICENSE_PLATE, DOMAIN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Car",
        domain=DOMAIN,
        data={CONF_LICENSE_PLATE: "11ZKZ3"},
        unique_id="11ZKZ3",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None, None, None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.rdw.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_rdw() -> Generator[AsyncMock, None, None]:
    """Return a mocked RDW client."""
    with (
        patch("homeassistant.components.rdw.RDW", autospec=True) as rdw_mock,
        patch("homeassistant.components.rdw.config_flow.RDW", new=rdw_mock),
    ):
        rdw = rdw_mock.return_value
        rdw.vehicle.return_value = Vehicle.from_json(load_fixture("rdw/11ZKZ3.json"))
        yield rdw
