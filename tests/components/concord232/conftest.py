"""Fixtures for the Concord232 integration."""

from collections.abc import Generator
from unittest.mock import MagicMock, create_autospec, patch

from concord232 import client as concord232_client
import pytest

from homeassistant.components.concord232.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_concord232_client_class() -> Generator[MagicMock]:
    """Mock the concord232 Client class.

    The class is patched in the library module itself, so constructor
    calls from the platforms and the config flow all resolve to the same
    class mock and share one instance.
    """
    mock_client_class = create_autospec(concord232_client.Client)
    with patch("concord232.client.Client", new=mock_client_class):
        mock_instance = mock_client_class.return_value
        mock_instance.list_partitions.return_value = [{"arming_level": "Off"}]
        mock_instance.list_zones.return_value = [
            {"number": 1, "name": "FRONT DOOR", "state": "Normal"},
            {"number": 2, "name": "HALL MOTION", "state": "Normal"},
        ]
        yield mock_client_class


@pytest.fixture
def mock_concord232_client(mock_concord232_client_class: MagicMock) -> MagicMock:
    """Return the mocked concord232 client instance."""
    return mock_concord232_client_class.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="localhost",
        data={CONF_HOST: "localhost", CONF_PORT: 5007},
    )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration from a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
