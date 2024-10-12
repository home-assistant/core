"""Fixtures for Palazzetti integration tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.palazzetti.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="palazzetti",
        domain=DOMAIN,
        data={CONF_HOST: "example"},
        unique_id="unique_thingy",
    )


@pytest.fixture
def mock_palazzetti():
    """Return a mocked Palazzetti Hub."""
    with patch("homeassistant.components.palazzetti.coordinator.Hub") as palazetti_mock:
        client = palazetti_mock.return_value
        yield client
