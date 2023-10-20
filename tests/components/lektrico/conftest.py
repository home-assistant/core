"""Fixtures for Lektrico Charging Station integration tests."""
import pytest

from homeassistant.components.lektrico.const import DOMAIN
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="test",
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1", CONF_FRIENDLY_NAME: "test"},
    )
