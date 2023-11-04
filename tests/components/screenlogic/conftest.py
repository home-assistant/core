"""Setup fixtures for ScreenLogic integration tests."""
import pytest

from homeassistant.components.screenlogic import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL

from . import MOCK_ADAPTER_IP, MOCK_ADAPTER_MAC, MOCK_ADAPTER_NAME, MOCK_ADAPTER_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        title=MOCK_ADAPTER_NAME,
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: MOCK_ADAPTER_IP,
            CONF_PORT: MOCK_ADAPTER_PORT,
        },
        options={
            CONF_SCAN_INTERVAL: 30,
        },
        unique_id=MOCK_ADAPTER_MAC,
        entry_id="screenlogictest",
    )
