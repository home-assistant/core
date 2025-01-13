"""Configure tests for the Onkyo integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.onkyo.const import DOMAIN

from . import create_connection

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create Onkyo entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Onkyo",
        data={},
    )


@pytest.fixture(autouse=True)
def patch_timeouts():
    """Patch timeouts to avoid tests waiting."""
    with patch.multiple(
        "homeassistant.components.onkyo.receiver",
        DEVICE_INTERVIEW_TIMEOUT=0,
        DEVICE_DISCOVERY_TIMEOUT=0,
    ):
        yield


@pytest.fixture
async def default_mock_discovery():
    """Mock discovery with a single device."""

    async def mock_discover(host=None, discovery_callback=None, timeout=0):
        await discovery_callback(create_connection(1))

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        new=mock_discover,
    ):
        yield


@pytest.fixture
async def stub_mock_discovery():
    """Mock discovery with no devices."""

    async def mock_discover(host=None, discovery_callback=None, timeout=0):
        pass

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        new=mock_discover,
    ):
        yield


@pytest.fixture
async def empty_mock_discovery():
    """Mock discovery with an empty connection."""

    async def mock_discover(host=None, discovery_callback=None, timeout=0):
        await discovery_callback(None)

    with patch(
        "homeassistant.components.onkyo.receiver.pyeiscp.Connection.discover",
        new=mock_discover,
    ):
        yield
