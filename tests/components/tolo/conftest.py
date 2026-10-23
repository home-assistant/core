"""Fixtures for the TOLO Sauna tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tololib import LampMode

from homeassistant.components.tolo.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a TOLO Sauna config entry."""
    return MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "127.0.0.1"})


@pytest.fixture
def mock_tolo_client() -> Generator[MagicMock]:
    """Mock the TOLO client used by the coordinator."""
    with patch(
        "homeassistant.components.tolo.coordinator.ToloClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.get_status.return_value = MagicMock(lamp_on=True)
        client.get_status.return_value.model.name = "SAUNA"
        client.get_settings.return_value = MagicMock(lamp_mode=LampMode.MANUAL)
        yield client
