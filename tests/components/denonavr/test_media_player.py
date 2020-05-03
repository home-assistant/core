"""The tests for the denonavr media player platform."""
from unittest.mock import patch, Mock, MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components import media_player
from homeassistant.components.denonavr import ATTR_COMMAND, SERVICE_GET_COMMAND
from homeassistant.components.denonavr.config_flow import DOMAIN, CONF_SHOW_ALL_SOURCES, CONF_ZONE2, CONF_ZONE3
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_TIMEOUT, CONF_PLATFORM
from homeassistant.setup import async_setup_component

TEST_NAME = "fake"
TEST_RECEIVER_ID = "model-serialnumeber123"
TEST_HOST = "1.2.3.4"
TEST_TIMEOUT = 2
TEST_SHOW_ALL_SOURCES = False
TEST_ZONE2 = False
TEST_ZONE3 = False
ENTITY_ID = f"{media_player.DOMAIN}.{TEST_NAME}"


#@pytest.fixture(name="client")
#def client_fixture():
#    """Patch of client library for tests."""
#    with patch(
#        "homeassistant.components.denonavr.receiver.denonavr.DenonAVR",
#        autospec=True,
#    ) as mock_client_class, patch(
#        "homeassistant.components.denonavr.receiver.denonavr.discover"
#    ):
#        mock_client_class.return_value.name = TEST_NAME
#        mock_client_class.return_value.zones = {"Main": mock_client_class.return_value}
#        yield mock_client_class.return_value

def get_mock_receiver():
    """Return a mock receiver instance."""
    receiver = Mock()
    zone_main = Mock()
    
    zone_main.name = TEST_NAME
    zone_main.netaudio_func_list = []
    zone_main.sound_mode_list = []
    zone_main.input_func_list = []
    zone_main.playing_func_list = []
    zone_main.volume = 20
    zone_main.send_get_command = MagicMock()
    
    receiver.name = TEST_NAME
    receiver.zones = {"Main": zone_main}

    return receiver

async def setup_denonavr(hass, mock_receiver):
    """Initialize media_player for tests."""
    entry_data = {
        CONF_HOST: TEST_HOST,
        CONF_TIMEOUT: TEST_TIMEOUT,
        CONF_SHOW_ALL_SOURCES: TEST_SHOW_ALL_SOURCES,
        CONF_ZONE2: TEST_ZONE2,
        CONF_ZONE3: TEST_ZONE3,
        "receiver_id": TEST_RECEIVER_ID,
    }
    
    config_entry = config_entries.ConfigEntry(
        1,
        DOMAIN,
        "Mock Title",
        entry_data,
        TEST_NAME,
        config_entries.CONN_CLASS_LOCAL_POLL,
        system_options={},
    )
    
    assert await async_setup_component(hass, DOMAIN, {}) is True

    hass.data[DOMAIN] = {config_entry.entry_id: mock_receiver}
    await hass.config_entries.async_forward_entry_setup(config_entry, "media_player")
    # To flush out the service call to update the group
    await hass.async_block_till_done()


async def test_get_command(hass):
    """Test generic command functionality."""
    mock_receiver = get_mock_receiver()
    await setup_denonavr(hass, mock_receiver)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test",
    }
    await hass.services.async_call(DOMAIN, SERVICE_GET_COMMAND, data)
    await hass.async_block_till_done()

    mock_receiver.send_get_command.assert_called_with("test")
