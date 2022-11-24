"""espspencer session fixtures."""
import pytest

from spencerassistant.components.espspencer import CONF_NOISE_PSK, DOMAIN
from spencerassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from spencerassistant.core import spencerAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def espspencer_mock_async_zeroconf(mock_async_zeroconf):
    """Auto mock zeroconf."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="ESPspencer Device",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.2",
            CONF_PORT: 6053,
            CONF_PASSWORD: "pwd",
            CONF_NOISE_PSK: "12345678123456781234567812345678",
        },
        unique_id="espspencer-device",
    )


@pytest.fixture
async def init_integration(
    hass: spencerAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the ESPspencer integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
