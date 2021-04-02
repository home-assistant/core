"""The tests for the denonavr media player platform."""
from unittest.mock import patch

import pytest

from homeassistant.components import media_player
from homeassistant.components.denonavr.config_flow import (
    CONF_MANUFACTURER,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_TYPE,
    DOMAIN,
)
from homeassistant.components.denonavr.media_player import (
    ATTR_COMMAND,
    SERVICE_GET_COMMAND,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_NAME = "Test_Receiver"
TEST_MODEL = "model5"
TEST_SERIALNUMBER = "123456789"
TEST_MANUFACTURER = "Denon"
TEST_RECEIVER_TYPE = "avr-x"
TEST_ZONE = "Main"
TEST_UNIQUE_ID = f"{TEST_MODEL}-{TEST_SERIALNUMBER}"
TEST_TIMEOUT = 2
TEST_SHOW_ALL_SOURCES = False
TEST_ZONE2 = False
TEST_ZONE3 = False
ENTITY_ID = f"{media_player.DOMAIN}.{TEST_NAME}"


@pytest.fixture(name="client")
def client_fixture():
    """Patch of client library for tests."""
    with patch(
        "homeassistant.components.denonavr.receiver.DenonAVR",
        autospec=True,
    ) as mock_client_class, patch(
        "homeassistant.components.denonavr.config_flow.denonavr.async_discover"
    ):
        mock_client_class.return_value.name = TEST_NAME
        mock_client_class.return_value.model_name = TEST_MODEL
        mock_client_class.return_value.serial_number = TEST_SERIALNUMBER
        mock_client_class.return_value.manufacturer = TEST_MANUFACTURER
        mock_client_class.return_value.receiver_type = TEST_RECEIVER_TYPE
        mock_client_class.return_value.zone = TEST_ZONE
        mock_client_class.return_value.input_func_list = []
        mock_client_class.return_value.sound_mode_list = []
        mock_client_class.return_value.zones = {"Main": mock_client_class.return_value}
        yield mock_client_class.return_value


async def setup_denonavr(hass):
    """Initialize media_player for tests."""
    entry_data = {
        CONF_HOST: TEST_HOST,
        CONF_MODEL: TEST_MODEL,
        CONF_TYPE: TEST_RECEIVER_TYPE,
        CONF_MANUFACTURER: TEST_MANUFACTURER,
        CONF_SERIAL_NUMBER: TEST_SERIALNUMBER,
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_UNIQUE_ID,
        data=entry_data,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)

    assert state
    assert state.name == TEST_NAME


async def test_get_command(hass, client):
    """Test generic command functionality."""
    await setup_denonavr(hass)

    data = {
        ATTR_ENTITY_ID: ENTITY_ID,
        ATTR_COMMAND: "test_command",
    }
    await hass.services.async_call(DOMAIN, SERVICE_GET_COMMAND, data)
    await hass.async_block_till_done()

    client.async_get_command.assert_awaited_with("test_command")
