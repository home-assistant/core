"""Fixtures for the Zendure integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from zendure import Availability, DeviceSnapshot

from homeassistant.components.zendure.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

SERIAL_NUMBER = "TESTDEV00000001"


def build_snapshot(fixture: str = "device_snapshot.json") -> DeviceSnapshot:
    """Build a device snapshot from a fixture of decoded values."""
    data = load_json_object_fixture(fixture, DOMAIN)
    return DeviceSnapshot(
        serial_number=data["serial_number"],
        model_key=data["model_key"],
        product_raw=data["product_raw"],
        availability=Availability.ONLINE,
        properties=data["properties"],
        protocol_version=data["protocol_version"],
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="SolarFlow 2400 AC+",
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.50"},
        unique_id=SERIAL_NUMBER,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.zendure.async_setup_entry", return_value=None
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_read() -> AsyncMock:
    """Return the mocked device read, to change what the device reports."""
    return AsyncMock(return_value=build_snapshot())


@pytest.fixture
def mock_zendure(mock_read: AsyncMock) -> Generator[MagicMock]:
    """Return a mocked Zendure client shared by setup and the config flow."""
    client = MagicMock()
    client.async_refresh = mock_read
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)
    with (
        patch(
            "homeassistant.components.zendure.create_local_client",
            return_value=client,
        ) as factory,
        patch(
            "homeassistant.components.zendure.config_flow.create_local_client",
            new=factory,
        ),
    ):
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zendure: MagicMock,
) -> MockConfigEntry:
    """Set up the Zendure integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
