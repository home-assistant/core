"""Fixtures for RDW integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from vehicle import Vehicle

from homeassistant.components.rdw.const import CONF_LICENSE_PLATE, DOMAIN
from homeassistant.core import HomeAssistant

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
def mock_rdw_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked RDW client."""
    with patch(
        "homeassistant.components.rdw.config_flow.RDW", autospec=True
    ) as rdw_mock:
        rdw = rdw_mock.return_value
        rdw.vehicle.return_value = Vehicle.from_json(load_fixture("rdw/11ZKZ3.json"))
        yield rdw


@pytest.fixture
def mock_rdw(request: pytest.FixtureRequest) -> Generator[None, MagicMock, None]:
    """Return a mocked WLED client."""
    fixture: str = "rdw/11ZKZ3.json"
    if hasattr(request, "param") and request.param:
        fixture = request.param

    vehicle = Vehicle.from_json(load_fixture(fixture))
    with patch("homeassistant.components.rdw.RDW", autospec=True) as rdw_mock:
        rdw = rdw_mock.return_value
        rdw.vehicle.return_value = vehicle
        yield rdw


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_rdw: MagicMock
) -> MockConfigEntry:
    """Set up the RDW integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
