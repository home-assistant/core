"""Test the Qbittorrent Init."""

from unittest.mock import MagicMock, patch

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant import setup
from homeassistant.components import qbittorrent
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

test_url = "http://testurl.org"
test_username = "test-username"
test_password = "test-password"

MOCK_ENTRY = MockConfigEntry(
    domain=qbittorrent.DOMAIN,
    data={
        qbittorrent.CONF_URL: test_url,
        qbittorrent.CONF_USERNAME: test_username,
        qbittorrent.CONF_PASSWORD: test_password,
    },
    unique_id=test_url,
)


def _create_mocked_client(raise_request_exception=False, raise_login_exception=False):
    mocked_client = MagicMock()
    if raise_request_exception:
        mocked_client.login.side_effect = RequestException("Mocked Exception")
    if raise_login_exception:
        mocked_client.login.side_effect = LoginRequired()
    return mocked_client


async def test_import_old_config_sensor(hass: HomeAssistant):
    """Test import of old sensor platform config."""
    config = {
        "sensor": [
            {
                CONF_PLATFORM: qbittorrent.DOMAIN,
                CONF_URL: test_url,
                CONF_USERNAME: test_username,
                CONF_PASSWORD: test_password,
            }
        ],
    }
    mocked_client = _create_mocked_client(False, False)
    with patch(
        "homeassistant.components.qbittorrent.client.Client",
        return_value=mocked_client,
    ):
        with patch("homeassistant.core.ServiceRegistry.async_call", return_value=True):
            assert await setup.async_setup_component(hass, "sensor", config)
            await hass.async_block_till_done()

            confflow_entries = hass.config_entries.flow.async_progress(True)

            assert len(confflow_entries) == 1


async def test_import_faulty_config_sensor(hass: HomeAssistant):
    """Test import of old sensor platform config."""
    config = {
        "sensor": [
            {
                CONF_PLATFORM: qbittorrent.DATA_KEY_NAME,
            }
        ],
    }
    mocked_client = _create_mocked_client(False, False)
    with patch(
        "homeassistant.components.qbittorrent.client.Client",
        return_value=mocked_client,
    ):
        with patch("homeassistant.core.ServiceRegistry.async_call", return_value=True):
            assert await setup.async_setup_component(hass, "sensor", config)
            await hass.async_block_till_done()

            confflow_entries = hass.config_entries.flow.async_progress(True)

            assert len(confflow_entries) == 0


async def test_unload_entry(hass: HomeAssistant):
    """Test removing Qbittorrent client."""
    mocked_client = _create_mocked_client(False, False)
    with patch(
        "homeassistant.components.qbittorrent.client.Client", return_value=mocked_client
    ):
        entry = MOCK_ENTRY
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.NOT_LOADED
