"""Fixtures for OpenRGB integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import jsonpickle
import pytest

from homeassistant.components.openrgb.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Computer",
        data={
            CONF_NAME: "Test Computer",
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 6742,
        },
        entry_id="01J0EXAMPLE0CONFIGENTRY00",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.openrgb.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_openrgb_device() -> MagicMock:
    """Return a mocked OpenRGB device."""
    json = load_fixture("device_ene_dram.json", DOMAIN)
    obj = jsonpickle.decode(json)

    device = MagicMock(spec=obj)
    for name, value in vars(obj).items():
        setattr(device, name, value)

    # Methods
    device.set_color = MagicMock()
    device.set_mode = MagicMock()

    return device


@pytest.fixture
def mock_openrgb_client(mock_openrgb_device: MagicMock) -> Generator[MagicMock]:
    """Return a mocked OpenRGB client."""
    with (
        patch(
            "homeassistant.components.openrgb.coordinator.OpenRGBClient",
            autospec=True,
        ) as client_mock,
        patch(
            "homeassistant.components.openrgb.config_flow.OpenRGBClient",
            new=client_mock,
        ),
    ):
        client = client_mock.return_value

        # Attributes
        client.protocol_version = 4
        client.devices = [mock_openrgb_device]

        # Methods
        client.update = MagicMock()
        client.connect = MagicMock()
        client.disconnect = MagicMock()

        # Store the class mock so tests can set side_effect
        client.client_class_mock = client_mock

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_openrgb_client: MagicMock,
) -> MockConfigEntry:
    """Set up the OpenRGB integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
